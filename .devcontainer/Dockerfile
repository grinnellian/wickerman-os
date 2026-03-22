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
        iptables ipset iproute2 dnsutils \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
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

# Firewall script
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# Workspace
RUN mkdir -p /workspace && chown $USERNAME:$USERNAME /workspace
WORKDIR /workspace

# Command history persistence
RUN mkdir -p /commandhistory \
    && chown $USERNAME:$USERNAME /commandhistory \
    && echo 'export HISTFILE=/commandhistory/.bash_history' >> /home/$USERNAME/.bashrc \
    && echo 'HISTSIZE=10000' >> /home/$USERNAME/.bashrc \
    && echo 'SAVEHIST=10000' >> /home/$USERNAME/.zshrc \
    && echo 'HISTFILE=/commandhistory/.zsh_history' >> /home/$USERNAME/.zshrc

USER $USERNAME
