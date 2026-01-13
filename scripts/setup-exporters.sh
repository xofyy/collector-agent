#!/bin/bash
# Exporter Setup Script for Ubuntu 22.04 LTS
# Installs Node Exporter and checks nvidia-smi availability

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

# Node Exporter version
NODE_EXPORTER_VERSION="1.7.0"

# ============================================
# Install Node Exporter
# ============================================
install_node_exporter() {
    echo_info "Installing Node Exporter v${NODE_EXPORTER_VERSION}..."
    
    # Check if already installed
    if systemctl is-active --quiet node_exporter; then
        echo_warn "Node Exporter is already running"
        return
    fi
    
    # Download
    cd /tmp
    wget -q "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
    
    # Extract
    tar xzf "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
    
    # Install binary
    cp "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter" /usr/local/bin/
    chmod +x /usr/local/bin/node_exporter
    
    # Create user
    if ! id -u node_exporter &>/dev/null; then
        useradd --no-create-home --shell /bin/false node_exporter
    fi
    
    # Create systemd service
    cat > /etc/systemd/system/node_exporter.service << 'EOF'
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter \
    --collector.systemd \
    --collector.processes

[Install]
WantedBy=multi-user.target
EOF
    
    # Cleanup
    rm -rf "/tmp/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64"*
    
    # Start service
    systemctl daemon-reload
    systemctl enable node_exporter
    systemctl start node_exporter
    
    echo_info "Node Exporter installed and started on port 9100"
}

# ============================================
# Check nvidia-smi
# ============================================
check_nvidia_smi() {
    echo_info "Checking nvidia-smi availability..."
    
    if command -v nvidia-smi &> /dev/null; then
        echo_info "nvidia-smi found at: $(which nvidia-smi)"
        
        # Test nvidia-smi
        if nvidia-smi --query-gpu=name --format=csv,noheader &> /dev/null; then
            echo_info "nvidia-smi is working correctly"
            
            # Show GPU info
            echo ""
            echo_info "Detected GPU(s):"
            nvidia-smi --query-gpu=index,name,driver_version --format=csv,noheader | while read line; do
                echo "  $line"
            done
            echo ""
        else
            echo_warn "nvidia-smi is installed but not working"
            echo_warn "GPU metrics will not be available"
        fi
    else
        echo_warn "nvidia-smi not found"
        echo_warn "GPU metrics will not be available"
        echo_warn "Install NVIDIA drivers to enable GPU monitoring"
    fi
}

# ============================================
# Main
# ============================================
echo_info "=========================================="
echo_info "Exporter Setup for Ubuntu 22.04 LTS"
echo_info "=========================================="
echo ""

# Install Node Exporter
install_node_exporter

echo ""

# Check nvidia-smi for GPU metrics
check_nvidia_smi

echo ""
echo_info "=========================================="
echo_info "Setup completed!"
echo_info "=========================================="
echo ""
echo "Verify Node Exporter:"
echo "  curl -s http://localhost:9100/metrics | head"
echo "  systemctl status node_exporter"
echo ""
echo "GPU metrics are collected via nvidia-smi (no additional setup required)"
echo "The collector agent will automatically use nvidia-smi if available."
echo ""
