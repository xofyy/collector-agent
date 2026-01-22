#!/bin/bash
# Collector Agent Update Script
# For Ubuntu 22.04 LTS
#
# Usage:
#   sudo ./scripts/update.sh              # Update to latest
#   sudo ./scripts/update.sh --backup     # Create backup only
#   sudo ./scripts/update.sh --rollback   # Rollback to previous version

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

readonly CONFIG_DIR="/etc/collector-agent"
readonly CONFIG_FILE="${CONFIG_DIR}/config.yaml"
readonly BACKUP_DIR="/var/lib/collector-agent/backups"
readonly LOG_FILE="/var/log/collector-agent.log"
readonly SERVICE_NAME="collector-agent"

# Options
OPT_BACKUP_ONLY=false
OPT_ROLLBACK=false
OPT_FORCE=false
OPT_NO_RESTART=false

# =============================================================================
# Colors and Output
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

echo_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
echo_step()    { echo -e "${BLUE}[STEP]${NC} $1"; }
echo_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

# =============================================================================
# Helper Functions
# =============================================================================

check_root() {
    if [[ "$EUID" -ne 0 ]]; then
        echo_error "Please run as root (sudo $SCRIPT_NAME)"
        exit 1
    fi
}

command_exists() {
    command -v "$1" &> /dev/null
}

service_is_active() {
    systemctl is-active --quiet "$1" 2>/dev/null
}

get_installed_version() {
    if command_exists collector; then
        collector version 2>/dev/null | grep -oP 'v\K[0-9.]+' || echo "unknown"
    else
        echo "not-installed"
    fi
}

get_project_version() {
    if [[ -f "${PROJECT_DIR}/collector/__init__.py" ]]; then
        grep -oP '__version__\s*=\s*"\K[^"]+' "${PROJECT_DIR}/collector/__init__.py" || echo "unknown"
    else
        echo "unknown"
    fi
}

# =============================================================================
# Usage
# =============================================================================

show_help() {
    cat << EOF
Collector Agent Update Script

Usage: $SCRIPT_NAME [OPTIONS]

Options:
    -h, --help        Show this help message
    -b, --backup      Create backup only (don't update)
    -r, --rollback    Rollback to previous backup
    -f, --force       Force update even if same version
    -n, --no-restart  Don't restart service after update

Examples:
    sudo $SCRIPT_NAME              # Update to latest version
    sudo $SCRIPT_NAME --backup     # Create config backup
    sudo $SCRIPT_NAME --rollback   # Restore previous config

Backup Location: ${BACKUP_DIR}
EOF
}

# =============================================================================
# Backup Functions
# =============================================================================

create_backup() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/config_${timestamp}.yaml"
    local version_file="${BACKUP_DIR}/version_${timestamp}.txt"

    echo_step "Creating backup..."

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    # Backup config if exists
    if [[ -f "$CONFIG_FILE" ]]; then
        cp "$CONFIG_FILE" "$backup_file"
        echo_info "Config backed up to: $backup_file"
    else
        echo_warn "No config file found to backup"
    fi

    # Record current version
    local current_version
    current_version=$(get_installed_version)
    echo "$current_version" > "$version_file"
    echo_info "Version recorded: $current_version"

    # Create latest symlink
    ln -sf "$backup_file" "${BACKUP_DIR}/config_latest.yaml" 2>/dev/null || true
    ln -sf "$version_file" "${BACKUP_DIR}/version_latest.txt" 2>/dev/null || true

    # Cleanup old backups (keep last 5)
    cleanup_old_backups

    echo_success "Backup completed"
}

cleanup_old_backups() {
    local backup_count
    backup_count=$(ls -1 "${BACKUP_DIR}"/config_*.yaml 2>/dev/null | wc -l)

    if [[ $backup_count -gt 5 ]]; then
        echo_info "Cleaning up old backups (keeping last 5)..."
        ls -1t "${BACKUP_DIR}"/config_*.yaml | tail -n +6 | xargs -r rm -f
        ls -1t "${BACKUP_DIR}"/version_*.txt | tail -n +6 | xargs -r rm -f
    fi
}

list_backups() {
    echo_step "Available backups:"
    if [[ -d "$BACKUP_DIR" ]]; then
        ls -lht "${BACKUP_DIR}"/config_*.yaml 2>/dev/null | head -5 || echo "  No backups found"
    else
        echo "  No backup directory found"
    fi
}

# =============================================================================
# Rollback Functions
# =============================================================================

do_rollback() {
    echo_step "Starting rollback..."

    local latest_backup="${BACKUP_DIR}/config_latest.yaml"

    if [[ ! -f "$latest_backup" ]]; then
        echo_error "No backup found to rollback to"
        list_backups
        exit 1
    fi

    # Stop service
    if service_is_active "$SERVICE_NAME"; then
        echo_info "Stopping service..."
        systemctl stop "$SERVICE_NAME"
    fi

    # Restore config
    echo_info "Restoring config from backup..."
    cp "$latest_backup" "$CONFIG_FILE"

    # Restart service
    echo_info "Starting service..."
    systemctl start "$SERVICE_NAME"

    # Verify
    sleep 2
    if service_is_active "$SERVICE_NAME"; then
        echo_success "Rollback completed successfully"
    else
        echo_error "Service failed to start after rollback"
        exit 1
    fi
}

# =============================================================================
# Update Functions
# =============================================================================

pre_update_checks() {
    echo_step "Pre-update checks..."

    # Check if installed
    if ! command_exists collector; then
        echo_error "Collector is not installed. Run install.sh first."
        exit 1
    fi

    # Check project files
    if [[ ! -f "${PROJECT_DIR}/pyproject.toml" ]]; then
        echo_error "Project files not found in ${PROJECT_DIR}"
        exit 1
    fi

    local installed_version project_version
    installed_version=$(get_installed_version)
    project_version=$(get_project_version)

    echo_info "Installed version: $installed_version"
    echo_info "Project version:   $project_version"

    if [[ "$installed_version" == "$project_version" ]] && [[ "$OPT_FORCE" == "false" ]]; then
        echo_warn "Already at version $project_version. Use --force to reinstall."
        exit 0
    fi
}

stop_service() {
    if service_is_active "$SERVICE_NAME"; then
        echo_step "Stopping service..."
        systemctl stop "$SERVICE_NAME"
        sleep 1
    fi
}

update_package() {
    echo_step "Updating Python package..."

    cd "$PROJECT_DIR"

    # Upgrade pip first (try with --break-system-packages for newer Ubuntu)
    pip3 install --upgrade pip --quiet --break-system-packages 2>/dev/null || \
    pip3 install --upgrade pip --quiet 2>/dev/null || true

    # Install/upgrade package
    if ! pip3 install --upgrade . --quiet --break-system-packages 2>/dev/null; then
        if ! pip3 install --upgrade . --quiet 2>/dev/null; then
            echo_error "Failed to update package"
            exit 1
        fi
    fi

    echo_info "Package updated"
}

start_service() {
    if [[ "$OPT_NO_RESTART" == "true" ]]; then
        echo_info "Skipping service restart (--no-restart)"
        return
    fi

    echo_step "Starting service..."
    systemctl daemon-reload
    systemctl start "$SERVICE_NAME"
    sleep 2
}

verify_update() {
    echo_step "Verifying update..."

    local new_version
    new_version=$(get_installed_version)
    echo_info "New version: $new_version"

    # Check service
    if [[ "$OPT_NO_RESTART" == "false" ]]; then
        if service_is_active "$SERVICE_NAME"; then
            echo_info "Service is running"
        else
            echo_error "Service is not running!"
            echo_warn "Check logs: journalctl -u $SERVICE_NAME -n 50"
            exit 1
        fi
    fi

    # Test CLI
    if collector version &>/dev/null; then
        echo_info "CLI is working"
    else
        echo_error "CLI test failed"
        exit 1
    fi

    echo_success "Update verified successfully"
}

do_update() {
    echo ""
    echo "=========================================="
    echo "  Collector Agent Update"
    echo "=========================================="
    echo ""

    pre_update_checks
    create_backup
    stop_service
    update_package
    start_service
    verify_update

    echo ""
    echo_success "Update completed successfully!"
    echo ""
    echo "Commands:"
    echo "  collector status     - Check status"
    echo "  collector metrics    - View metrics"
    echo "  sudo $SCRIPT_NAME --rollback  - Rollback if issues"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -b|--backup)
                OPT_BACKUP_ONLY=true
                shift
                ;;
            -r|--rollback)
                OPT_ROLLBACK=true
                shift
                ;;
            -f|--force)
                OPT_FORCE=true
                shift
                ;;
            -n|--no-restart)
                OPT_NO_RESTART=true
                shift
                ;;
            *)
                echo_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    check_root

    if [[ "$OPT_BACKUP_ONLY" == "true" ]]; then
        create_backup
        list_backups
    elif [[ "$OPT_ROLLBACK" == "true" ]]; then
        do_rollback
    else
        do_update
    fi
}

main "$@"
