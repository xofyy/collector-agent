# Collector Agent

Ubuntu 22.04 LTS üzerinde Node Exporter ve nvidia-smi'den sistem metriklerini toplayıp belirlenen endpoint'e gönderen Python CLI tabanlı metrik toplama ajanı.

## Özellikler

- **CPU**: Kullanım yüzdesi, load average, çekirdek sayısı, sıcaklık
- **RAM**: Toplam, kullanılan, kullanılabilir bellek
- **Disk**: Tüm mount point'ler için kullanım bilgisi
- **GPU**: NVIDIA GPU kullanımı, bellek, sıcaklık, güç tüketimi (nvidia-smi ile)
- **CLI**: Anlık metrik görüntüleme ve canlı izleme (`-f` flag)
- **Daemon**: Arka planda çalışma modu
- **Systemd**: Otomatik başlatma entegrasyonu

## Gereksinimler

- Ubuntu 22.04 LTS
- Python 3.10+
- Node Exporter (port 9100)
- NVIDIA Driver (GPU metrikleri için, opsiyonel)

## Kurulum

### GitHub'dan İndirme

```bash
# Repoyu klonla
git clone https://github.com/xofyy/collector-agent.git
cd collector-agent

# Veya zip olarak indir
wget https://github.com/xofyy/collector-agent/archive/main.zip
unzip main.zip
cd collector-agent-main
```

### Kurulum Adımları

```bash
# 1. Node Exporter kur ve nvidia-smi kontrolü yap
sudo ./scripts/setup-exporters.sh

# 2. Agent'ı kur (otomatik başlatır)
sudo ./scripts/install.sh
```

### Kurulum Seçenekleri

```bash
# Normal kurulum (otomatik başlatır)
sudo ./scripts/install.sh

# Başlatmadan kur
sudo ./scripts/install.sh --no-start

# Mevcut kurulumu kaldır
sudo ./scripts/install.sh --uninstall

# Zorla yeniden kur (config'i sıfırlar)
sudo ./scripts/install.sh --force

# Yardım
./scripts/install.sh --help
```

## Kullanım

### Servis Kontrolü

```bash
# Servis durumunu göster
collector status

# Foreground'da başlat
collector start

# Daemon olarak başlat
collector start --daemon

# Daemon'ı durdur
collector stop
```

### Metrik Görüntüleme

```bash
# Tüm metrikleri göster
collector metrics

# Canlı izleme (her 2 saniyede güncelle)
collector metrics -f

# Canlı izleme (özel interval)
collector metrics -f -i 5

# Kategori bazlı görüntüleme
collector metrics cpu
collector metrics gpu
collector metrics ram
collector metrics disk
collector metrics temp
```

### Konfigürasyon

```bash
# Mevcut ayarları göster
collector config show

# Endpoint ayarla
sudo collector config set endpoint http://localhost:8080/metrics

# Veri toplama aralığını ayarla (saniye)
sudo collector config set interval 30

# GPU metriklerini kapat
sudo collector config set exporters.nvidia_smi.enabled false

# Varsayılana sıfırla
sudo collector config reset
```

### Test

```bash
# Endpoint bağlantısını test et
collector test

# Sadece JSON çıktısını göster (göndermeden)
collector test --dry-run
```

## Konfigürasyon Dosyası

Konum: `/etc/collector-agent/config.yaml`

```yaml
endpoint: https://webhook-test.com/c4da883ab9f9086a6dbabbee56704e44
interval: 30

exporters:
  node_exporter:
    enabled: true
    url: http://localhost:9100/metrics
    timeout: 5
  nvidia_smi:
    enabled: true
    nvidia_smi_path: null  # Otomatik algıla

logging:
  level: INFO
  file: /var/log/collector-agent.log

daemon:
  pid_file: /var/run/collector-agent.pid
```

## Systemd Yönetimi

```bash
# Servis durumu
sudo systemctl status collector-agent

# Servisi başlat/durdur/yeniden başlat
sudo systemctl start collector-agent
sudo systemctl stop collector-agent
sudo systemctl restart collector-agent

# Otomatik başlatmayı etkinleştir/devre dışı bırak
sudo systemctl enable collector-agent
sudo systemctl disable collector-agent

# Logları görüntüle
sudo journalctl -u collector-agent -f
```

## GPU Metrikleri

GPU metrikleri `nvidia-smi` komutu ile toplanır:

- Tüm NVIDIA GPU'ları destekler (GeForce, Quadro, Tesla, RTX)
- Ek servis kurulumu gerektirmez
- NVIDIA driver kurulu olması yeterlidir
- nvidia-smi bulunamazsa GPU metrikleri atlanır, diğer metrikler toplanmaya devam eder

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

## Hızlı Başlangıç (Tek Satır)

```bash
git clone https://github.com/your-username/collector-agent.git && cd collector-agent && sudo ./scripts/setup-exporters.sh && sudo ./scripts/install.sh
```

## Kaldırma

```bash
sudo ./scripts/install.sh --uninstall --force
```

## Lisans

MIT
