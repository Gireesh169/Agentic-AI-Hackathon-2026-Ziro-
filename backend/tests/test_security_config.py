from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = [
    PROJECT_ROOT / "backend" / ".env.example",
    PROJECT_ROOT / "frontend" / ".env.example",
]


def test_example_environment_files_contain_placeholders_only():
    secret_patterns = (
        r"sk-[A-Za-z0-9_-]{20,}",
        r"sb_(?:secret|publishable)_[A-Za-z0-9_-]{20,}",
        r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",
    )

    for env_file in ENV_FILES:
        contents = env_file.read_text(encoding="utf-8")
        assert not any(re.search(pattern, contents) for pattern in secret_patterns), env_file

    backend_example = (PROJECT_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    assert "replace-with-your-openai-api-key" in backend_example
    assert "replace-with-your-supabase-server-side-secret" in backend_example


def test_frontend_does_not_reference_server_side_secret_names():
    frontend_root = PROJECT_ROOT / "frontend"
    forbidden_names = (
        "OPENAI_API_KEY",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    )

    for path in frontend_root.rglob("*"):
        if path.is_file() and "node_modules" not in path.parts and "dist" not in path.parts:
            contents = path.read_text(encoding="utf-8", errors="ignore")
            assert not any(name in contents for name in forbidden_names), path


def test_gitignore_excludes_local_env_and_generated_secret_files():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    for rule in (".env", ".env.*", "!.env.example", ".secrets/", "*.pem", "*.key"):
        assert rule in gitignore
