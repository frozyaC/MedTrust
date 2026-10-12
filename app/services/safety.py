from urllib.parse import urlparse

DEFAULT_SAFE_DOMAINS = {
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "nih.gov", "who.int", "cdc.gov",
    "fda.gov", "ema.europa.eu", "nice.org.uk", "nhs.uk", "medlineplus.gov",
    "mayoclinic.org", "msdmanuals.com", "minzdrav.gov.ru", "cr.minzdrav.gov.ru",
    "cochranelibrary.com", "bmj.com", "nejm.org", "jamanetwork.com", "thelancet.com",
}


def is_safe_domain(url: str, allowed_domains: set[str]) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname:
        return False
    return any(hostname == domain or hostname.endswith("." + domain) for domain in allowed_domains)
