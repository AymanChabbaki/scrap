"""
send_applications.py

Send an application email (with CV attached) to all contacts in a sector CSV.

Usage (PowerShell):
  python send_applications.py --csv by_sector\sector_developpement_informatique.csv --cv path\to\CV.pdf --your-name "Prénom Nom" --dry-run

Configuration:
  SMTP settings can be provided via environment variables or CLI flags:
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL

The script is conservative by default: use --dry-run to preview recipients and outputs
before actually sending emails. It logs successes/failures to `sent_log.csv`.
"""
import os
import csv
import time
import argparse
import smtplib
import ssl
from email.message import EmailMessage
from typing import List
import socket
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; if it's not installed the code will still use env vars
    pass


def test_smtp_connection(server: str, port: int, timeout: float = 5.0):
    if not server:
        return False, 'No SMTP server provided'
    try:
        # Resolve host
        addr_info = socket.getaddrinfo(server, port, proto=socket.IPPROTO_TCP)
        # Try connecting to the first resolved address
        for family, socktype, proto, canonname, sockaddr in addr_info:
            s = socket.socket(family, socktype, proto)
            s.settimeout(timeout)
            try:
                s.connect(sockaddr)
                s.close()
                return True, ''
            except Exception as e:
                last_err = e
                try:
                    s.close()
                except Exception:
                    pass
        return False, f'Could not connect to {server}:{port} - last error: {last_err}'
    except socket.gaierror as e:
        return False, f'DNS lookup failure for {server}: {e}'
    except Exception as e:
        return False, str(e)


# SMTP and identity values should come from environment variables or a .env file.
# See .env.example for required keys: SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL, CV_PATH, SECTOR_CSV, YOUR_NAME

def load_recipients(csv_path: str) -> List[dict]:
    """Read CSV and return list of full row dicts with at least 'EntrepriseContactEmail'.

    The returned dicts keep original CSV column names so templates can use them.
    """
    recipients = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            email = (r.get('EntrepriseContactEmail') or r.get('EntrepriseContactEmail'.lower()) or '').strip()
            if not email:
                continue
            # normalize keys: keep as-is but ensure common accessors
            row = {k: (v or '') for k, v in r.items()}
            # also expose short aliases
            row['email'] = email
            row['company'] = row.get('EntrepriseName', row.get('EntrepriseName'.lower(), ''))
            row['contact'] = row.get('EntrepriseContactName', row.get('EntrepriseContactName'.lower(), ''))
            recipients.append(row)

    # dedupe by email preserving order
    seen = set()
    out = []
    for r in recipients:
        e = r['email'].lower()
        if e in seen:
            continue
        seen.add(e)
        out.append(r)
    return out


DEFAULT_BODY = os.getenv('BODY_TEMPLATE') or (
    "Bonjour {contact_name},\n\n"
    "Je m'appelle {your_name} et je souhaite vous exprimer mon vif intérêt pour les activités de {company}. "
    "Votre travail dans ce domaine m’inspire particulièrement et j’aimerais savoir si vous avez des opportunités ou des besoins auxquels je pourrais contribuer.\n\n"
    "Je joins mon CV en pièce jointe. Je suis disponible pour un échange (visio ou téléphone) afin de vous présenter plus en détail mon expérience et la valeur que je peux apporter à votre équipe.\n\n"
    "Merci beaucoup pour votre temps et votre considération.\n\n"
    "Bien cordialement,\n"
    "{your_name}\n"
)


def create_message(from_addr: str, to_addr: str, subject: str, body: str, cv_path: str) -> EmailMessage:
    msg = EmailMessage()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.set_content(body)

    if cv_path:
        try:
            with open(cv_path, 'rb') as f:
                data = f.read()
            maintype = 'application'
            subtype = 'pdf'
            filename = os.path.basename(cv_path)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        except Exception as e:
            raise RuntimeError(f"Failed to attach CV: {e}")

    return msg


class SafeDict(dict):
    def __missing__(self, key):
        return ''


def send_smtp(server: str, port: int, user: str, password: str, msg: EmailMessage, use_tls=True):
    context = ssl.create_default_context()
    if use_tls:
        with smtplib.SMTP(server, port, timeout=60) as smtp:
            smtp.starttls(context=context)
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP_SSL(server, port, context=context, timeout=60) as smtp:
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=not bool(os.getenv('SECTOR_CSV')), default=os.getenv('SECTOR_CSV'), help='Sector CSV file (from by_sector)')
    parser.add_argument('--cv', required=not bool(os.getenv('CV_PATH')), default=os.getenv('CV_PATH'), help='Path to your CV (PDF recommended)')
    parser.add_argument('--your-name', required=not bool(os.getenv('YOUR_NAME')), default=os.getenv('YOUR_NAME'), help='Your full name to appear in the email')
    parser.add_argument('--from-email', help='From address (overrides SMTP user)')
    parser.add_argument('--subject', default=os.getenv('SUBJECT', 'Intérêt pour votre entreprise'), help='Email subject')
    parser.add_argument('--body-template', default=os.getenv('BODY_TEMPLATE', None), help='Body template (Python format) - placeholders from CSV columns')
    parser.add_argument('--list-vars', action='store_true', help='List available template variables from the CSV and exit')
    parser.add_argument('--delay', type=float, default=2.0, help='Seconds to wait between emails')
    parser.add_argument('--dry-run', action='store_true', help='Do not actually send emails; print preview')
    parser.add_argument('--smtp-server', help='SMTP server (or set SMTP_SERVER env)')
    parser.add_argument('--smtp-port', type=int, help='SMTP port (or set SMTP_PORT env)')
    parser.add_argument('--smtp-user', help='SMTP user (or set SMTP_USER env)')
    parser.add_argument('--smtp-pass', help='SMTP password (or set SMTP_PASS env)')
    parser.add_argument('--no-tls', action='store_true', help='Use SSL (no STARTTLS)')
    args = parser.parse_args()

    # Optionally just check SMTP connectivity and exit
    if getattr(args, 'check_smtp', False):
        # Resolve and test connection
        server = args.smtp_server or os.getenv('SMTP_SERVER') or (globals().get('SMTP_SERVER'))
        port = args.smtp_port or int(os.getenv('SMTP_PORT', str(globals().get('SMTP_PORT', 587))))
        ok, err = test_smtp_connection(server, port)
        if ok:
            print(f"SMTP connectivity OK: {server}:{port}")
            return
        else:
            print(f"SMTP connectivity FAILED: {err}")
            return

    # Prefer CLI args, then env vars, then top-of-file constants if present
    smtp_server = args.smtp_server or os.getenv('SMTP_SERVER') or (globals().get('SMTP_SERVER'))
    smtp_port = args.smtp_port or int(os.getenv('SMTP_PORT', str(globals().get('SMTP_PORT', 587))))
    smtp_user = args.smtp_user or os.getenv('SMTP_USER') or (globals().get('SMTP_USER'))
    smtp_pass = args.smtp_pass or os.getenv('SMTP_PASS') or (globals().get('SMTP_PASS'))
    from_email = args.from_email or os.getenv('FROM_EMAIL') or (globals().get('FROM_EMAIL')) or smtp_user

    def print_smtp_help(err_msg: str):
        print("\nSMTP connection error:\n  " + err_msg)
        print("Possible causes:")
        print(" - Wrong SMTP server hostname. For Gmail use smtp.gmail.com")
        print(" - No internet or DNS issues on this machine")
        print(" - Firewall blocking outbound SMTP ports (25/465/587)")
        print(" - Use app-specific password for Gmail/Outlook instead of account password")
        print("Set correct SMTP_SERVER/SMTP_PORT and retry.\n")

    # If actually sending (not dry-run), check SMTP connectivity first and fail fast with guidance
    if not args.dry_run:
        try:
            ok, err = test_smtp_connection(smtp_server, smtp_port)
        except Exception as e:
            ok, err = False, str(e)
        if not ok:
            print_smtp_help(err)
            return

    if not smtp_server and not args.dry_run:
        print('SMTP server not provided (use env SMTP_SERVER or --smtp-server). Aborting.')
        return

    recipients = load_recipients(args.csv)
    if not recipients:
        print('No recipients found in CSV.')
        return

    # If user requested variable listing, print CSV headers and example and exit
    if args.list_vars:
        headers = set(recipients[0].keys())
        # common convenience aliases added by the loader
        aliases = ['contact_name', 'company', 'your_name', 'email', 'contact', 'sector', 'sector_slug']
        print('Available variables (use in templates with {var_name}):')
        for h in sorted(headers):
            print(f' - {h}')
        print('\nAlso available aliases (always provided):')
        for a in aliases:
            print(f' - {a}')
        print('\nNote: the default SUBJECT and BODY_TEMPLATE are read from the environment variables SUBJECT and BODY_TEMPLATE.')
        return

    # derive sector from filename: e.g. by_sector/sector_bio_tech.csv -> 'bio tech'
    csv_basename = os.path.splitext(os.path.basename(args.csv))[0] if args.csv else ''
    sector_slug = csv_basename[len('sector_'):] if csv_basename.startswith('sector_') else csv_basename
    # human-friendly sector name
    sector_name = sector_slug.replace('_', ' ').strip()

    # attach sector info to each recipient row so templates can use {sector} and {sector_slug}
    for r in recipients:
        r.setdefault('sector', sector_name)
        r.setdefault('sector_slug', sector_slug)

    print(f'Found {len(recipients)} unique recipients in {args.csv}')

    log_path = 'sent_log.csv'
    if not args.dry_run:
        log_f = open(log_path, 'a', newline='', encoding='utf-8')
        log_writer = csv.writer(log_f)
        # header if empty
        if os.stat(log_path).st_size == 0:
            log_writer.writerow(['email', 'company', 'status', 'error'])
    else:
        log_f = None
        log_writer = None

    for r in recipients:
        contact_name = r['contact'] or ''
        company = r['company'] or ''
        to_addr = r['email']

        # Render body: prefer user-provided template, fallback to default template
        template = args.body_template or DEFAULT_BODY
        ctx = SafeDict({k: (v or '') for k, v in r.items()})
        # ensure common aliases exist
        ctx.setdefault('contact_name', contact_name or company)
        ctx.setdefault('company', company or '')
        ctx.setdefault('your_name', args.your_name)
        try:
            body = template.format_map(ctx)
        except Exception as e:
            print(f'Failed to render template for {to_addr}: {e}. Using fallback body.')
            body = DEFAULT_BODY.format(contact_name=contact_name or company, company=company or '', your_name=args.your_name)

        # Only attach CV if file exists. This prevents dry-run failures when CV is not present.
        attach_cv = args.cv if args.cv and os.path.exists(args.cv) else None
        if args.cv and not attach_cv:
            print(f"Warning: CV not found at {args.cv}; proceeding without attachment for preview/dry-run.")

        # Personalize and format subject using the same template context so env SUBJECT can use {sector}, {company}, etc.
        base_subject = args.subject or os.getenv('SUBJECT') or 'Intérêt pour votre entreprise'
        try:
            # Format with SafeDict to avoid KeyError on missing placeholders
            formatted_subject = base_subject.format_map(ctx if isinstance(ctx, dict) else dict(ctx))
        except Exception:
            formatted_subject = base_subject
        # If the original template didn't include {company} and we have a company, append it for clarity
        if '{company}' not in base_subject and company:
            subject_for_recipient = f"{formatted_subject} {company}"
        else:
            subject_for_recipient = formatted_subject

        try:
            msg = create_message(from_email, to_addr, subject_for_recipient, body, attach_cv)
        except Exception as e:
            print(f'Failed to prepare message for {to_addr}: {e}')
            if log_writer:
                log_writer.writerow([to_addr, company, 'prepare_failed', str(e)])
            continue

        print(f"Prepared: {to_addr} ({company})")
        if args.dry_run:
            continue

        try:
            send_smtp(smtp_server, smtp_port, smtp_user, smtp_pass, msg, use_tls=not args.no_tls)
            print(f"Sent: {to_addr}")
            if log_writer:
                log_writer.writerow([to_addr, company, 'sent', ''])
        except Exception as e:
            err_str = str(e)
            # Common DNS-resolution socket error
            if isinstance(e, socket.gaierror):
                err_str = f"DNS resolution failed for SMTP server: {e}"
            print(f"Failed to send to {to_addr}: {err_str}")
            if log_writer:
                log_writer.writerow([to_addr, company, 'error', err_str])

        time.sleep(args.delay)

    if log_f:
        log_f.close()


if __name__ == '__main__':
    main()
