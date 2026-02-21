#!/bin/bash

# Backup script
# Author: Your Name
# Date: YYYY-MM-DD

# Variables
BACKUP_DIR="/path/to/backup"
SOURCE_DIR="/path/to/source"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Perform the backup
tar -czf "$BACKUP_DIR/backup_$DATE.tar.gz" -C "$SOURCE_DIR" .

# Optional: Remove backups older than 7 days
find "$BACKUP_DIR" -type f -name "backup_*.tar.gz" -mtime +7 -exec rm {} \;.