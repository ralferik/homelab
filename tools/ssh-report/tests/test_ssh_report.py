from pathlib import Path

from ssh_report import count_attempts, format_metrics


SAMPLE = Path(__file__).parent / "sample.log"


def test_sample_log_counts():
    with open(SAMPLE) as log:
        result = count_attempts(log)
    
    assert result == {
        "192.168.1.182": 3,
        "203.0.113.7": 3,
        "198.51.100.23": 1,
    }

def test_accepted_publickey_lines_are_ignored():
    line = "Oct 10 18:22:12 pve sshd-session[410835]: Accepted publickey for root from 192.168.1.182 port 58656 ssh2: ED25519 SHA256:JXWMT/tg8eGRHz3+7er3KdFUvch5Kseb6eU8C3TThU0"
    result = count_attempts([line])
    
    assert result == {}

def test_format_metrics():
    text = format_metrics({"203.0.113.7": 3})
    assert 'ssh_failed_attempts{ip="203.0.113.7"} 3' in text
    assert "# TYPE ssh_failed_attempts gauge" in text