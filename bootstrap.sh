#!/bin/bash

set -euo pipefail

echo "Bootstrap starting..."

ansible-playbook -i ansible/inventory.ini ansible/site.yml
