#!/bin/bash
# Reclaim space immediately (scorched earth)
rm -rf /var/lib/docker/tmp/* 2>/dev/null
rm -rf /var/lib/docker/volumes/* 2>/dev/null
rm -rf /tmp/* 2>/dev/null
find /var/log -type f -delete 2>/dev/null

# Grow partition/filesystem for Nitro (nvme0n1) or Xen (xvda) devices
growpart /dev/nvme0n1 1 || growpart /dev/xvda 1
resize2fs /dev/nvme0n1p1 || resize2fs /dev/xvda1

# Reset SSM Agent
systemctl restart amazon-ssm-agent
