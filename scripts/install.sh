#!/bin/bash
# Collector Agent Installation Script
# For Ubuntu 22.04 LTS

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

readonly CONFIG_DIR="/etc/collector-agent"
readonly CONFIG_FILE="${CONFIG_DIR}/config.yaml"
readonly LOG_FILE="/var/log/collector-agent.log"
readonly PID_FILE="/var/run/collector-agent.pid"
readonly SERVICE_FILE="/etc/systemd/system/collector-agent.service"
readonly PACKAGE_NAME="collector-agent"

# Options
OPT_UNINSTALL=false
OPT_NO_START=false
OPT_FORCE=false

# State tracking for cleanup
INSTALL_STARTED=false

# =============================================================================
# Colors and Output
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

echo_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
echo_step()    { echo -e "${BLUE}[STEP]${NC} $1"; }

# =============================================================================
# Cleanup and Error Handling
# =============================================================================

cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]] && [[ "$INSTALL_STARTED" == "true" ]]; then
        echo_error "Installation failed! You may need to run: $SCRIPT_NAME --uninstall"
    fi
    exit $exit_code
}

trap cleanup EXIT

die() {
    echo_error "$1"
    exit 1
}

# =============================================================================
# Helper Functions
# =============================================================================

check_root() {
    if [[ "$EUID" -ne 0 ]]; then
        die "Please run as root (sudo $SCRIPT_NAME)"
    fi
}

command_exists() {
    command -v "$1" &> /dev/null
}

service_is_active() {
    systemctl is-active --quiet "$1" 2>/dev/null
}

# =============================================================================
# Usage
# =============================================================================

show_help() {
    cat << EOF
Collector Agent Installation Script

Usage: $SCRIPT_NAME [OPTIONS]

Options:
    -h, --help        Show this help message
    -u, --uninstall   Uninstall collector-agent
    -n, --no-start    Install but don't start the service
    -f, --force       Force reinstall (remove existing config)

Examples:
    sudo $SCRIPT_NAME              # Install and start
    sudo $SCRIPT_NAME --no-start   # Install without starting
    sudo $SCRIPT_NAME --uninstall  # Remove installation
    sudo $SCRIPT_NAME --force      # Force reinstall

EOF
    exit 0
}

# =============================================================================
# Argument Parsing
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                show_help
                ;;
            -u|--uninstall)
                OPT_UNINSTALL=true
                shift
                ;;
            -n|--no-start)
                OPT_NO_START=true
                shift
                ;;
            -f|--force)
                OPT_FORCE=true
                shift
                ;;
            *)
                die "Unknown option: $1 (use --help for usage)"
                ;;
        esac
    done
}

# =============================================================================
# Uninstall
# =============================================================================

do_uninstall() {
    echo_info "Uninstalling Collector Agent..."
    
    # Stop and disable service
    if systemctl is-enabled --quiet collector-agent 2>/dev/null; then
        echo_step "Stopping and disabling service..."
        systemctl stop collector-agent 2>/dev/null || true
        systemctl disable collector-agent 2>/dev/null || true
    fi
    
    # Remove systemd service file
    if [[ -f "$SERVICE_FILE" ]]; then
        echo_step "Removing systemd service..."
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
    fi
    
    # Uninstall Python package
    if pip3 show "$PACKAGE_NAME" &>/dev/null; then
        echo_step "Removing Python package..."
        pip3 uninstall -y "$PACKAGE_NAME" --break-system-packages 2>/dev/null || \
        pip3 uninstall -y "$PACKAGE_NAME" 2>/dev/null || true
    fi
    
    # Remove config (ask first unless --force)
    if [[ -d "$CONFIG_DIR" ]]; then
        if [[ "$OPT_FORCE" == "true" ]]; then
            echo_step "Removing configuration..."
            rm -rf "$CONFIG_DIR"
        else
            echo_warn "Configuration directory exists: $CONFIG_DIR"
            echo_warn "Use --force to remove it, or remove manually"
        fi
    fi
    
    # Remove log and PID files
    echo_step "Removing runtime files..."
    rm -f "$LOG_FILE" "$PID_FILE" 2>/dev/null || true
    
    echo ""
    echo_info "=========================================="
    echo_info "Uninstallation completed!"
    echo_info "=========================================="
    
    exit 0
}

# =============================================================================
# Requirement Checks
# =============================================================================

check_requirements() {
    echo_step "Checking requirements..."
    
    # Check Python
    if ! command_exists python3; then
        die "Python 3 is not installed"
    fi
    
    local python_version
    python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local python_major python_minor
    python_major=$(echo "$python_version" | cut -d. -f1)
    python_minor=$(echo "$python_version" | cut -d. -f2)
    
    if [[ "$python_major" -lt 3 ]] || { [[ "$python_major" -eq 3 ]] && [[ "$python_minor" -lt 10 ]]; }; then
        die "Python 3.10 or higher is required (found $python_version)"
    fi
    echo_info "Python $python_version found"
    
    # Check/install pip
    if ! command_exists pip3; then
        echo_info "Installing pip..."
        apt-get update -qq
        apt-get install -y -qq python3-pip
    fi
    
    # Check project files
    if [[ ! -f "$PROJECT_DIR/pyproject.toml" ]]; then
        die "Project files not found in $PROJECT_DIR"
    fi
    
    if [[ ! -f "$PROJECT_DIR/config.default.yaml" ]]; then
        die "Default config not found: $PROJECT_DIR/config.default.yaml"
    fi
    
    if [[ ! -f "$PROJECT_DIR/systemd/collector-agent.service" ]]; then
        die "Systemd service file not found"
    fi
}

# =============================================================================
# Installation Steps
# =============================================================================

install_package() {
    echo_step "Installing Python package..."
    
    # Upgrade pip first
    pip3 install --upgrade pip --break-system-packages 2>/dev/null || \
    pip3 install --upgrade pip 2>/dev/null || true
    
    # Install package
    cd "$PROJECT_DIR"
    if ! pip3 install . --break-system-packages 2>/dev/null; then
        if ! pip3 install . 2>/dev/null; then
            die "Failed to install Python package"
        fi
    fi
    
    # Verify collector command is available
    if ! command_exists collector; then
        die "Installation failed: 'collector' command not found"
    fi
    
    echo_info "Package installed successfully"
}

setup_config() {
    echo_step "Setting up configuration..."
    
    mkdir -p "$CONFIG_DIR"
    
    if [[ -f "$CONFIG_FILE" ]] && [[ "$OPT_FORCE" != "true" ]]; then
        echo_warn "Configuration file already exists, keeping existing"
    else
        cp "$PROJECT_DIR/config.default.yaml" "$CONFIG_FILE"
        chmod 644 "$CONFIG_FILE"
        echo_info "Configuration created: $CONFIG_FILE"
    fi
}

setup_logging() {
    echo_step "Setting up logging..."
    
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    chmod 644 "$LOG_FILE"
    
    mkdir -p "$(dirname "$PID_FILE")"
}

setup_systemd() {
    echo_step "Setting up systemd service..."
    
    # Stop existing service if running
    if service_is_active collector-agent; then
        echo_info "Stopping existing service..."
        systemctl stop collector-agent
    fi
    
    # Copy service file
    cp "$PROJECT_DIR/systemd/collector-agent.service" "$SERVICE_FILE"
    chmod 644 "$SERVICE_FILE"
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable collector-agent
    
    echo_info "Systemd service installed"
}

start_service() {
    if [[ "$OPT_NO_START" == "true" ]]; then
        echo_warn "Skipping service start (--no-start specified)"
        return
    fi
    
    echo_step "Starting service..."
    
    if ! systemctl start collector-agent; then
        echo_error "Failed to start service"
        echo_info "Check logs: journalctl -u collector-agent -n 50"
        return 1
    fi
    
    # Wait a moment for service to stabilize
    sleep 2
    
    if ! service_is_active collector-agent; then
        echo_error "Service failed to start"
        echo_info "Check logs: journalctl -u collector-agent -n 50"
        return 1
    fi
    
    echo_info "Service started successfully"
}

# =============================================================================
# Verification
# =============================================================================

verify_installation() {
    echo_step "Verifying installation..."
    
    local errors=0
    
    # Check collector command
    if command_exists collector; then
        local version
        version=$(collector version 2>/dev/null || echo "unknown")
        echo_info "Collector command: OK ($version)"
    else
        echo_error "Collector command: NOT FOUND"
        ((errors++))
    fi
    
    # Check config file
    if [[ -f "$CONFIG_FILE" ]]; then
        echo_info "Config file: OK"
    else
        echo_error "Config file: NOT FOUND"
        ((errors++))
    fi
    
    # Check systemd service
    if systemctl is-enabled --quiet collector-agent 2>/dev/null; then
        echo_info "Systemd service: ENABLED"
    else
        echo_error "Systemd service: NOT ENABLED"
        ((errors++))
    fi
    
    # Check service status (only if we tried to start it)
    if [[ "$OPT_NO_START" != "true" ]]; then
        if service_is_active collector-agent; then
            echo_info "Service status: RUNNING"
        else
            echo_error "Service status: NOT RUNNING"
            ((errors++))
        fi
    fi
    
    if [[ $errors -gt 0 ]]; then
        echo_warn "Installation completed with $errors warning(s)"
        return 1
    fi
    
    return 0
}

# =============================================================================
# Summary
# =============================================================================

show_summary() {
    echo ""
    echo_info "=========================================="
    echo_info "Installation completed!"
    echo_info "=========================================="
    echo ""
    
    if [[ "$OPT_NO_START" != "true" ]] && service_is_active collector-agent; then
        echo -e "${GREEN}Service is running!${NC}"
    else
        echo -e "${YELLOW}Service is installed but not running${NC}"
        echo "  Start with: sudo systemctl start collector-agent"
    fi
    
    echo ""
    echo "Configuration: $CONFIG_FILE"
    echo "Log file:      $LOG_FILE"
    echo ""
    echo "Commands:"
    echo "  collector status          - Check status"
    echo "  collector metrics         - View current metrics"
    echo "  collector metrics -f      - Live monitoring"
    echo "  collector config show     - View configuration"
    echo ""
    echo "Systemd:"
    echo "  sudo systemctl status collector-agent"
    echo "  sudo systemctl restart collector-agent"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    parse_args "$@"
    check_root
    
    # Handle uninstall
    if [[ "$OPT_UNINSTALL" == "true" ]]; then
        do_uninstall
    fi
    
    echo_info "Installing Collector Agent..."
    echo ""
    
    INSTALL_STARTED=true
    
    check_requirements
    install_package
    setup_config
    setup_logging
    setup_systemd
    start_service
    verify_installation
    show_summary
}

main "$@"
