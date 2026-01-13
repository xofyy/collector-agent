# Collector Agent

Ubuntu 22.04 LTS üzerinde Node Exporter ve nvidia-smi'den sistem metriklerini toplayıp yerel Docker endpoint'ine gönderen Python CLI tabanlı bir agent.

## Özellikler

- CPU kullanımı, load average ve sıcaklık
- RAM kullanımı
- Disk kullanımı (tüm mount point'ler)
- NVIDIA GPU kullanımı, bellek ve sıcaklık (nvidia-smi ile)
- CLI ile anlık metrik görüntüleme
- Daemon modu ile arka planda çalışma
- Systemd entegrasyonu

## Gereksinimler

- Ubuntu 22.04 LTS
- Python 3.10+
- Node Exporter (port 9100)
- NVIDIA Driver (nvidia-smi için, opsiyonel)

## Kurulum

```bash
# Node Exporter kur ve nvidia-smi kontrolü yap
sudo ./scripts/setup-exporters.sh

# Agent'ı kur
sudo ./scripts/install.sh
```

## Kullanım

### Servis Kontrolü

```bash
# Foreground'da başlat
collector start

# Daemon olarak başlat
collector start --daemon

# Daemon'ı durdur
collector stop

# Servis durumu
collector status
```

### Metrik Görüntüleme

```bash
# Tüm metrikleri göster
collector metrics

# Kategori bazlı
collector metrics cpu
collector metrics gpu
collector metrics ram
collector metrics disk
```

### Konfigürasyon

```bash
# Mevcut config'i göster
collector config show

# Endpoint ayarla
collector config set endpoint http://localhost:8080/metrics

# Interval ayarla (saniye)
collector config set interval 30
```

### Test

```bash
# Endpoint'e test isteği gönder
collector test

# Sadece JSON çıktısını göster, gönderme
collector test --dry-run
```

## Konfigürasyon

Config dosyası: `/etc/collector-agent/config.yaml`

```yaml
endpoint: http://localhost:8080/metrics
interval: 30

exporters:
  node_exporter:
    enabled: true
    url: http://localhost:9100/metrics
    timeout: 5
  nvidia_smi:
    enabled: true
    nvidia_smi_path: null  # Auto-detect

logging:
  level: INFO
  file: /var/log/collector-agent.log

daemon:
  pid_file: /var/run/collector-agent.pid
```

## GPU Metrikleri

GPU metrikleri `nvidia-smi` komutu kullanılarak toplanır. Bu yöntem:

- Tüm NVIDIA GPU'ları destekler (GeForce, Quadro, Tesla, RTX)
- Ek servis kurulumu gerektirmez
- NVIDIA driver kurulu olması yeterlidir

nvidia-smi bulunamazsa GPU metrikleri atlanır, diğer metrikler toplanmaya devam eder.

## Systemd

```bash
# Servisi başlat
sudo systemctl start collector-agent

# Otomatik başlatmayı etkinleştir
sudo systemctl enable collector-agent

# Durumu kontrol et
sudo systemctl status collector-agent

# Logları görüntüle
sudo journalctl -u collector-agent -f
```

## JSON Çıktı Formatı

```json
{
    "timestamp": "2026-01-13T14:30:00Z",
    "hostname": "kiosk-042",
    "cpu": {
        "usage_percent": 45.2,
        "load_1m": 1.5,
        "load_5m": 1.2,
        "load_15m": 0.9,
        "cores": 4,
        "temperature_celsius": 52.0
    },
    "memory": {
        "total_bytes": 17179869184,
        "available_bytes": 8589934592,
        "usage_percent": 50.0
    },
    "disks": [
        {
            "mountpoint": "/",
            "device": "/dev/sda1",
            "total_bytes": 274877906944,
            "available_bytes": 137438953472,
            "usage_percent": 50.0
        }
    ],
    "gpu": {
        "utilization_percent": 35.0,
        "memory_used_bytes": 4294967296,
        "memory_total_bytes": 12884901888,
        "memory_usage_percent": 33.3,
        "temperature_celsius": 48.0,
        "power_watts": 120.5
    }
}
```

## Lisans

MIT
