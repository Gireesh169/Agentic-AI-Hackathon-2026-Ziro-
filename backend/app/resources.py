import re
import ipaddress
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

CATALOG = [
    {
        "id": "spring-guides",
        "title": "Spring Guides — Building a RESTful Web Service",
        "url": "https://spring.io/guides/gs/rest-service/",
        "topics": ["java", "spring", "spring boot", "rest", "api", "backend"],
        "note": "Official Spring guide for building a RESTful web service."
    },
    {
        "id": "spring-reference",
        "title": "Spring Boot Reference Documentation",
        "url": "https://docs.spring.io/spring-boot/reference/",
        "topics": ["spring", "spring boot", "dependency injection", "configuration", "backend"],
        "note": "Official Spring Boot reference documentation."
    },
    {
        "id": "dev-java",
        "title": "Dev.java Learning Resources",
        "url": "https://dev.java/learn/",
        "topics": ["java", "oop", "collections", "exceptions", "programming"],
        "note": "Official Java learning resources."
    },
    {
        "id": "postgresql-docs",
        "title": "PostgreSQL Documentation",
        "url": "https://www.postgresql.org/docs/",
        "topics": ["postgresql", "sql", "database", "jpa", "backend"],
        "note": "Official PostgreSQL documentation."
    },
    {
        "id": "git-book",
        "title": "Pro Git Book",
        "url": "https://git-scm.com/book/en/v2",
        "topics": ["git", "version control", "software development", "deployment"],
        "note": "Free online Pro Git book."
    },
    {
        "id": "sqlbolt",
        "title": "SQLBolt — Interactive SQL Lessons",
        "url": "https://sqlbolt.com/",
        "topics": ["sql", "database", "query", "joins", "aggregation"],
        "note": "Public interactive SQL lessons; verify current page and access conditions."
    },
    {
        "id": "kaggle-learn",
        "title": "Kaggle Learn",
        "url": "https://www.kaggle.com/learn",
        "topics": ["python", "pandas", "data visualization", "machine learning", "data analysis"],
        "note": "Public learning catalog; verify the specific lesson and account requirements."
    },
    {
        "id": "python-tutorial",
        "title": "Python Official Tutorial",
        "url": "https://docs.python.org/3/tutorial/",
        "topics": ["python", "programming", "fundamentals"],
        "note": "Official Python documentation."
    },
    {
        "id": "pandas-getting-started",
        "title": "pandas Getting Started",
        "url": "https://pandas.pydata.org/docs/getting_started/index.html",
        "topics": ["pandas", "data cleaning", "data analysis", "dataframes"],
        "note": "Official pandas documentation."
    },
    {
        "id": "microsoft-learn",
        "title": "Microsoft Learn",
        "url": "https://learn.microsoft.com/training/",
        "topics": ["power bi", "excel", "visualization", "dashboard", "data analyst"],
        "note": "Microsoft technical learning catalog; verify the specific learning path."
    },
]

PAID_TERMS = [
    "free trial", "subscription required", "paid subscription", "purchase this course",
    "buy this course", "upgrade to premium", "payment required"
]
FREE_TERMS = [
    "free course", "free training", "free learning path", "free tutorials",
    "free to learn", "free online course"
]
MATCH_STOPWORDS = {
    "api", "backend", "data", "deployment", "fundamentals", "learning",
    "programming", "project", "resources", "software",
}

def find_resources(topic: str, limit: int = 3):
    words = set(re.findall(r"[a-z0-9]+", topic.lower())) - MATCH_STOPWORDS
    ranked = []
    for item in CATALOG:
        tags = set(" ".join(item["topics"]).lower().split()) - MATCH_STOPWORDS
        score = len(words & tags)
        if score > 0:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if not ranked:
        return []
    return [dict(item, verification_status="NOT_CHECKED", evidence=None) for _, item in ranked[:limit]]

def classify_pricing(text: str, catalog_candidate: bool = False):
    normalized = re.sub(r"\s+", " ", text.lower())
    if any(term in normalized for term in PAID_TERMS):
        return "PAID", "Pricing text matched a paid-access indicator; manual review may still be needed."
    if any(term in normalized for term in FREE_TERMS):
        return "FREE", "Page text explicitly matched a free-learning indicator; recheck before use."
    if catalog_candidate:
        return "UNKNOWN", "Known public learning source, but extracted page text did not establish current course pricing."
    return "UNKNOWN", "Could not establish whether the learning content is free from the extracted page text."

def is_safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().strip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        return False
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))]
        except Exception:
            # DNS failures will be handled by the HTTP check; do not allow known local names.
            return True
    return all(address.is_global for address in addresses)

def verify_resource(url: str, simulate: str = "none", catalog_candidate: bool = False):
    checked_at = datetime.now(timezone.utc).isoformat()
    if simulate == "paid":
        return {
            "url": url, "http_status": 200, "link_status": "LIVE",
            "pricing_status": "PAID", "checked_at": checked_at,
            "evidence": "Deterministic TC2 fixture: simulated pricing changed to paid.",
            "final_url": url
        }
    if simulate == "broken":
        return {
            "url": url, "http_status": 404, "link_status": "BROKEN",
            "pricing_status": "UNKNOWN", "checked_at": checked_at,
            "evidence": "Deterministic TC3 fixture: simulated HTTP 404.",
            "final_url": url
        }
    parsed = urlparse(url)
    if not is_safe_public_url(url):
        return {
            "url": url, "http_status": None, "link_status": "INVALID",
            "pricing_status": "UNKNOWN", "checked_at": checked_at,
            "evidence": "Only public HTTP(S) URLs are allowed; local/private network targets are blocked.", "final_url": url
        }
    try:
        with httpx.Client(follow_redirects=True, timeout=8.0, headers={"User-Agent": "FreeLearningPathBuilder/1.0 (educational demo)"}) as client:
            response = client.get(url)
        status = response.status_code
        final_url = str(response.url)
        if status >= 400:
            return {
                "url": url, "http_status": status, "link_status": "BROKEN",
                "pricing_status": "UNKNOWN", "checked_at": checked_at,
                "evidence": f"HTTP request returned status {status}.",
                "final_url": final_url
            }
        soup = BeautifulSoup(response.text[:1_000_000], "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        page_text = soup.get_text(" ", strip=True)[:100_000]
        pricing_status, pricing_evidence = classify_pricing(page_text, catalog_candidate)
        return {
            "url": url, "http_status": status, "link_status": "LIVE",
            "pricing_status": pricing_status, "checked_at": checked_at,
            "evidence": pricing_evidence, "final_url": final_url,
            "page_title": (soup.title.get_text(" ", strip=True) if soup.title else "")[:250]
        }
    except Exception as exc:
        return {
            "url": url, "http_status": None, "link_status": "UNKNOWN",
            "pricing_status": "UNKNOWN", "checked_at": checked_at,
            "evidence": f"Request failed: {type(exc).__name__}: {str(exc)[:180]}",
            "final_url": url
        }
