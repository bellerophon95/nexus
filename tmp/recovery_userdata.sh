#!/bin/bash
growpart /dev/nvme0n1 1 || growpart /dev/xvda 1
resize2fs /dev/nvme0n1p1 || resize2fs /dev/xvda1
docker system prune -af --volumes
find /var/log -type f -regex ".*\.[0-9]\|.*\.gz" -delete
