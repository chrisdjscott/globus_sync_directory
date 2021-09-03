import logging
import subprocess


def send_email(email_list, subject, message):
    """
    Send email message

    """
    logger = logging.getLogger("email")
    logger.info(f'Sending email "{subject}" to {",".join(email_list)}')
    cmdargs = ["/usr/bin/mail", "-s", f'"{subject}"', "--"]
    cmdargs.extend(email_list)
    cmd = " ".join(cmdargs)
    logger.debug(f"email command: {cmd}")
    status = subprocess.run(cmd, shell=True, universal_newlines=True, input=message)
    if status.returncode:
        logger.warning("Warning: sending email failed")
        logger.warning(cmd)
