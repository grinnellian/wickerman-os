FROM python:3.11-slim

ARG TZ=America/Los_Angeles
ARG CLAUDE_CODE_VERSION=latest
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=$USER_UID

ENV TZ=${TZ} \
    DEVCONTAINER=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System packages: git, networking, shell, Node.js (for Claude Code)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates sudo make \
        zsh nano vim less jq \
        iptables tinyproxy iproute2 dnsutils \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/zsh $USERNAME \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/$USERNAME

# Install Claude Code globally
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Install Python dev tooling
RUN pip install --no-cache-dir \
    pytest>=8.0 \
    pytest-cov>=5.0 \
    ruff>=0.4 \
    mypy>=1.10

# Forward proxy config (tinyproxy) and firewall script
COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY allowlist.conf /etc/tinyproxy/allowlist
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# Workspace and Claude config dir (volume mount target, must be owned by dev user)
RUN mkdir -p /workspace /home/$USERNAME/.claude \
    && chown $USERNAME:$USERNAME /workspace /home/$USERNAME/.claude
WORKDIR /workspace

# Command history persistence
RUN mkdir -p /commandhistory \
    && chown $USERNAME:$USERNAME /commandhistory \
    && echo 'export HISTFILE=/commandhistory/.bash_history' >> /home/$USERNAME/.bashrc \
    && echo 'HISTSIZE=10000' >> /home/$USERNAME/.bashrc \
    && echo 'SAVEHIST=10000' >> /home/$USERNAME/.zshrc \
    && echo 'HISTFILE=/commandhistory/.zsh_history' >> /home/$USERNAME/.zshrc

# Git: use GH_TOKEN env var for HTTPS push when available
RUN printf '#!/bin/sh\nif [ -n "$GH_TOKEN" ]; then\n  echo "protocol=https"\n  echo "host=github.com"\n  echo "username=x-access-token"\n  echo "password=$GH_TOKEN"\nfi\n' \
    > /usr/local/bin/git-credential-env && chmod +x /usr/local/bin/git-credential-env \
    && git config --system credential.helper /usr/local/bin/git-credential-env

USER $USERNAME
