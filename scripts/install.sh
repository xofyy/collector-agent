#!/bin/bash
# Collector Agent Installation Script
# For Ubuntu 22.04 LTS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo_error "Please run as root (sudo)"
    exit 1
fi

echo_info "Installing Collector Agent..."

# Check Python version
echo_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo_error "Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo_error "Python 3.10 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi
echo_info "Python $PYTHON_VERSION found"

# Install pip if not available
if ! command -v pip3 &> /dev/null; then
    echo_info "Installing pip..."
    apt-get update
    apt-get install -y python3-pip
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Upgrade pip for PEP 660 support (editable installs)
echo_info "Upgrading pip..."
pip3 install --upgrade pip --break-system-packages 2>/dev/null || pip3 install --upgrade pip

# Install the package
echo_info "Installing collector-agent package..."
cd "$PROJECT_DIR"
pip3 install . --break-system-packages 2>/dev/null || pip3 install .

# Create config directory
echo_info "Creating configuration directory..."
mkdir -p /etc/collector-agent

# Copy default config if not exists
if [ ! -f /etc/collector-agent/config.yaml ]; then
    echo_info "Creating default configuration..."
    cp "$PROJECT_DIR/config.default.yaml" /etc/collector-agent/config.yaml
else
    echo_warn "Configuration file already exists, skipping..."
fi

# Create log directory
echo_info "Creating log directory..."
mkdir -p /var/log
touch /var/log/collector-agent.log
chmod 644 /var/log/collector-agent.log

# Create PID directory
mkdir -p /var/run

# Install systemd service
echo_info "Installing systemd service..."
cp "$PROJECT_DIR/systemd/collector-agent.service" /etc/systemd/system/
systemctl daemon-reload

# Enable but don't start
echo_info "Enabling service..."
systemctl enable collector-agent

echo ""
echo_info "=========================================="
echo_info "Installation completed!"
echo_info "=========================================="
echo ""
echo "Configuration file: /etc/collector-agent/config.yaml"
echo "Log file: /var/log/collector-agent.log"
echo ""
echo "Before starting, make sure to:"
echo "  1. Configure the endpoint in /etc/collector-agent/config.yaml"
echo "  2. Install Node Exporter: ./scripts/setup-exporters.sh"
echo ""
echo "Commands:"
echo "  collector start           - Start in foreground"
echo "  collector start --daemon  - Start as daemon"
echo "  collector status          - Check status"
echo "  collector metrics         - View current metrics"
echo "  collector config show     - View configuration"
echo ""
echo "Systemd:"
echo "  sudo systemctl start collector-agent"
echo "  sudo systemctl status collector-agent"
echo ""
