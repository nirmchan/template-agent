.PHONY: local dev test clean deploy undeploy demo demo-down demo-clean demo-logs

# OpenShift namespace (can be overridden: make deploy openshift NAMESPACE=my-project)
NAMESPACE ?= $(shell oc project -q 2>/dev/null)

# Dependency checks
deps:
	@which uv > /dev/null && echo "uv: $(shell uv --version)" || (echo "Error: uv not found. Please install uv." && exit 1)
	@which podman > /dev/null && echo "podman: $(shell podman --version)" || (echo "Error: podman not found. Please install podman." && exit 1)
	@which podman-compose > /dev/null && echo "podman-compose: $(shell podman-compose --version)" || (echo "Error: podman-compose not found. Please install podman-compose." && exit 1)
	@which oc > /dev/null && echo "oc: $(shell oc version --client)" || (echo "Error: oc not found. Please install oc." && exit 1)

# Install Python dependencies
install:
	@echo "Creating virtual environment..."
	@test -d .venv || uv venv
	@echo "Installing package with dev dependencies..."
	@. .venv/bin/activate && uv pip install -e ".[dev]"
	@echo "Installing pre-commit hooks..."
	@. .venv/bin/activate && pre-commit install
	@echo "Python dependencies installed successfully!"
	@echo "Activating virtual environment..."
	@echo '#!/bin/bash' > /tmp/activate_and_shell.sh
	@echo 'source .venv/bin/activate' >> /tmp/activate_and_shell.sh
	@echo 'echo "Virtual environment activated! Type exit to return to your original shell."' >> /tmp/activate_and_shell.sh
	@echo 'exec "$$SHELL"' >> /tmp/activate_and_shell.sh
	@chmod +x /tmp/activate_and_shell.sh
	@exec /tmp/activate_and_shell.sh

clean:
	@echo "Cleaning up non-code artifacts..."
	@rm -rf .venv
	@rm -rf __pycache__
	@rm -rf .pytest_cache
	@rm -rf .coverage
	@rm -rf htmlcov
	@rm -rf .mypy_cache
	@rm -rf .ruff_cache
	@rm -rf build
	@rm -rf dist
	@rm -rf *.egg-info
	@rm -f Current-IT-Root-CAs.pem
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "Cleanup complete"

test:
	@if [ ! -d ".venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make install' first to set up the environment."; \
		exit 1; \
	fi
	.venv/bin/python -m pytest tests/unit

test-all:
	@if [ ! -d ".venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make install' first to set up the environment."; \
		exit 1; \
	fi
	@echo "Running all tests (unit + skills evals)..."
	.venv/bin/python -m pytest

test-skills:
	@if [ ! -d ".venv" ]; then \
		echo "Error: Virtual environment not found. Run 'make install' first to set up the environment."; \
		exit 1; \
	fi
	@echo "Running skills evaluations..."
	.venv/bin/python -m pytest tests/skills -m skills -v

eval-promptfoo:
	@echo "Running Promptfoo agent evaluations..."
	@echo "Make sure agent is running at http://localhost:5002"
	@cd config/agent/evals/promptfoo && npx promptfoo@latest eval

mock-mcp:
	@echo "Starting Mock MCP Server..."
	@./scripts/start-mock-mcp.sh

local-with-mock:
	@echo "This will start both Mock MCP Server and Agent"
	@echo "Run in separate terminals:"
	@echo "  Terminal 1: make mock-mcp"
	@echo "  Terminal 2: make local"
	@echo ""
	@echo "Or use podman-compose to run everything together"

local:
	@echo "Setting up local environment..."
	@test -f .env || (echo "Creating .env from .env.example..." && cp .env.example .env)
	@echo "Starting agent with LangGraph Platform..."
	@echo "API available at: http://localhost:5002"
	@echo "Press Ctrl+C to stop the server"
	@. .venv/bin/activate && aegra dev --port 5002

container:
	export PODMAN_COMPOSE_SILENT=true
	podman-compose --no-ansi up --build --force-recreate --remove-orphans  --timeout=60

# ---------------------------------------------------------------------------
# Development environment targets
# ---------------------------------------------------------------------------

dev: ## Start full dev stack with all services (Redis, Postgres, Langfuse, Jaeger)
	@echo "Starting development stack..."
	@echo "Services: pgvector, redis, jaeger, template-agent"
	@echo "Agent:    http://localhost:5002"
	@echo "Jaeger:   http://localhost:16686"
	@echo ""
	@test -f .env || (echo "Creating .env from .env.example..." && cp .env.example .env)
	podman-compose -f compose.dev.yaml up --build -d
	@echo ""
	@echo "Tailing agent logs (Ctrl+C to stop)..."
	@echo ""
	podman-compose -f compose.dev.yaml logs -f template-agent

dev-down: ## Stop dev stack
	podman-compose -f compose.dev.yaml down

dev-clean: ## Stop dev stack and remove all data
	podman-compose -f compose.dev.yaml down -v
	@echo "All dev data volumes removed"

dev-logs: ## Tail all service logs
	podman-compose -f compose.dev.yaml logs -f

dev-restart: ## Restart dev stack
	podman-compose -f compose.dev.yaml restart

dev-agent: ## Restart just the agent service
	podman-compose -f compose.dev.yaml restart template-agent

# ---------------------------------------------------------------------------
# Demo environment: Agent + MCP Server with SSO auth
# ---------------------------------------------------------------------------

DEMO_DIR := .demo
DEMO_MCP_REPO := https://github.com/redhat-data-and-ai/template-mcp-server.git
DEMO_MCP_BRANCH := deep-agent

demo: ## Start demo: agent + MCP server with SSO auth (end-to-end)
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║  Demo: Template Agent + MCP Server with SSO Authentication  ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@# --- Step 1: Clone MCP server if needed ---
	@if [ ! -d "$(DEMO_DIR)/template-mcp-server" ]; then \
		echo "Cloning template-mcp-server (branch: $(DEMO_MCP_BRANCH))..."; \
		mkdir -p $(DEMO_DIR); \
		git clone --branch $(DEMO_MCP_BRANCH) --depth 1 $(DEMO_MCP_REPO) $(DEMO_DIR)/template-mcp-server; \
	else \
		echo "MCP server already cloned at $(DEMO_DIR)/template-mcp-server"; \
	fi
	@# --- Step 2: Ensure agent .env exists ---
	@test -f .env || (echo "Creating .env from .env.example..." && cp .env.example .env)
	@# --- Step 3: Generate MCP server .env from agent's SSO config ---
	@echo "Generating MCP server .env from agent SSO config..."
	@SSO_ISSUER=$$(grep -E '^SSO_ISSUER_URL=' .env | cut -d'=' -f2- | tr -d '"' | tr -d "'"); \
	SSO_CID=$$(grep -E '^SSO_CLIENT_ID=' .env | cut -d'=' -f2- | tr -d '"' | tr -d "'"); \
	SSO_CSEC=$$(grep -E '^SSO_CLIENT_SECRET=' .env | cut -d'=' -f2- | tr -d '"' | tr -d "'"); \
	echo "# Auto-generated by make demo — do not edit" > $(DEMO_DIR)/mcp-server.env; \
	echo "MCP_HOST=0.0.0.0" >> $(DEMO_DIR)/mcp-server.env; \
	echo "MCP_PORT=5001" >> $(DEMO_DIR)/mcp-server.env; \
	echo "MCP_TRANSPORT_PROTOCOL=http" >> $(DEMO_DIR)/mcp-server.env; \
	echo "ENABLE_AUTH=True" >> $(DEMO_DIR)/mcp-server.env; \
	echo "PYTHON_LOG_LEVEL=INFO" >> $(DEMO_DIR)/mcp-server.env; \
	echo "SSO_CLIENT_ID=$$SSO_CID" >> $(DEMO_DIR)/mcp-server.env; \
	echo "SSO_CLIENT_SECRET=$$SSO_CSEC" >> $(DEMO_DIR)/mcp-server.env; \
	echo "SSO_CALLBACK_URL=http://localhost:5001/auth/callback/oidc" >> $(DEMO_DIR)/mcp-server.env; \
	echo "SSO_AUTHORIZATION_URL=$${SSO_ISSUER}/protocol/openid-connect/auth" >> $(DEMO_DIR)/mcp-server.env; \
	echo "SSO_TOKEN_URL=$${SSO_ISSUER}/protocol/openid-connect/token" >> $(DEMO_DIR)/mcp-server.env; \
	echo "SSO_INTROSPECTION_URL=$${SSO_ISSUER}/protocol/openid-connect/token/introspect" >> $(DEMO_DIR)/mcp-server.env; \
	echo "MCP server .env generated (SSO endpoints derived from SSO_ISSUER_URL)"
	@# --- Step 4: Generate Postgres init script (creates mcp_server DB) ---
	@echo "CREATE DATABASE mcp_server;" > $(DEMO_DIR)/init-databases.sql
	@# --- Step 5: Generate demo MCP config (container hostname) ---
	@echo '{"mcpServers":{"template-mcp-server":{"url":"http://template-mcp-server:5001/mcp/","transport":"streamable_http","enabled":true,"auth":true,"ssl_verify":false,"timeout":30}}}' | python3 -m json.tool > $(DEMO_DIR)/mcp.json
	@# --- Step 6: Stop dev stack if running ---
	@podman-compose -f compose.dev.yaml down 2>/dev/null || true
	@# --- Step 7: Start demo stack ---
	@echo ""
	@echo "Services: pgvector, redis, jaeger, template-mcp-server, template-agent"
	@echo "MCP Server: http://localhost:5001 (SSO auth enabled)"
	@echo "Agent:      http://localhost:5002"
	@echo "Jaeger:     http://localhost:16686"
	@echo ""
	podman-compose -f compose.demo.yaml up --build -d
	@echo ""
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════╗"
	@echo "║  Demo running! Token flow: User → Agent → MCP Server   ║"
	@echo "╚══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Tailing agent + MCP server logs (Ctrl+C to stop)..."
	@echo ""
	@trap 'kill 0 2>/dev/null' EXIT; \
		podman logs -f --names demo-mcp-server & \
		podman logs -f --names demo-agent & \
		wait

demo-down: ## Stop demo stack
	podman-compose -f compose.demo.yaml down

demo-clean: ## Stop demo stack, remove data, and clean local project
	podman-compose -f compose.demo.yaml down -v 2>/dev/null || true
	rm -rf $(DEMO_DIR)
	@podman rmi template-agent_template-mcp-server template-agent_template-agent 2>/dev/null || true
	@echo "Demo stopped, volumes removed, cloned repo cleaned"

demo-logs: ## Tail agent + MCP server logs
	@trap 'kill 0 2>/dev/null' EXIT; \
		podman logs -f --names demo-mcp-server & \
		podman logs -f --names demo-agent & \
		wait

# Deployment targets
deploy:
	@if [ "$(filter openshift,$(MAKECMDGOALS))" != "openshift" ] && [ "$(filter mpp,$(MAKECMDGOALS))" != "mpp" ]; then \
		echo "Usage: make deploy [openshift|mpp]"; \
		echo "Available deployment targets: openshift, mpp"; \
		exit 1; \
	fi

openshift:
	@echo "Checking for oc CLI..."
	@which oc > /dev/null || (echo "Error: oc CLI not found. Please install OpenShift CLI." && exit 1)
	@echo "Validating namespace..."
	@if [ -z "$(NAMESPACE)" ]; then \
		echo "Error: NAMESPACE not set. Usage: make deploy openshift NAMESPACE=your-project"; \
		exit 1; \
	fi; \
	echo "Using namespace: $(NAMESPACE)"; \
	echo "Switching to namespace..."; \
	oc project $(NAMESPACE) || (echo "Error: Cannot switch to namespace '$(NAMESPACE)'. Check permissions." && exit 1); \
	echo "Updating namespace references..."; \
	sed -i.bak "s|NAMESPACE_PLACEHOLDER|$(NAMESPACE)|g" deployment/overlays/openshift/deployment.yaml; \
	sed -i.bak "s|namespace: agent|namespace: $(NAMESPACE)|g" deployment/overlays/openshift/kustomization.yaml; \
	echo "Creating BuildConfig and ImageStream..."; \
	oc apply -f deployment/overlays/openshift/buildconfig.yaml; \
	oc apply -f deployment/overlays/openshift/imagestream.yaml; \
	echo "Building container image from source..."; \
	oc start-build agent --from-dir=. \
		--exclude='(^|/)\.venv(/|$$)' \
		--exclude='(^|/)__pycache__(/|$$)' \
		--exclude='(^|/)\.pytest_cache(/|$$)' \
		--exclude='(^|/)tests(/|$$)' \
		--exclude='(^|/)examples(/|$$)' \
		--exclude='(^|/)\.mypy_cache(/|$$)' \
		--exclude='(^|/)\.ruff_cache(/|$$)' \
		--exclude='.*\.log$$' \
		--follow || (mv deployment/overlays/openshift/deployment.yaml.bak deployment/overlays/openshift/deployment.yaml 2>/dev/null; mv deployment/overlays/openshift/kustomization.yaml.bak deployment/overlays/openshift/kustomization.yaml 2>/dev/null; exit 1); \
	echo "Deploying resources to OpenShift..."; \
	oc apply -k deployment/overlays/openshift/ || (mv deployment/overlays/openshift/deployment.yaml.bak deployment/overlays/openshift/deployment.yaml 2>/dev/null; mv deployment/overlays/openshift/kustomization.yaml.bak deployment/overlays/openshift/kustomization.yaml 2>/dev/null; exit 1); \
	rm -f deployment/overlays/openshift/deployment.yaml.bak deployment/overlays/openshift/kustomization.yaml.bak; \
	echo "Deployment complete!"; \
	echo "Checking deployment status..."; \
	oc get pods -l app=agent; \
	echo ""; \
	echo "Useful commands:"; \
	echo "  View logs: oc logs -l app=agent --tail=100"; \
	echo "  Get route: oc get route agent"; \
	echo "  Check status: oc get pods,svc,route -l app=agent"

mpp:
	@echo "Checking for oc CLI..."
	@which oc > /dev/null || (echo "Error: oc CLI not found. Please install OpenShift CLI." && exit 1)
	@echo "Validating TENANT parameter..."
	@if [ -z "$(TENANT)" ]; then \
		echo "Error: TENANT not set. Usage: make deploy mpp TENANT=your-tenant"; \
		exit 1; \
	fi; \
	CONFIG_NAMESPACE="$(TENANT)--config"; \
	RUNTIME_NAMESPACE="$(TENANT)--template"; \
	echo "Config namespace: $$CONFIG_NAMESPACE"; \
	echo "Runtime namespace: $$RUNTIME_NAMESPACE"; \
	echo "Updating tenant.yaml with config namespace..."; \
	sed -i.bak "s|TENANT_PLACEHOLDER|$$CONFIG_NAMESPACE|g" deployment/mpp/tenant.yaml; \
	echo "Creating/switching to config namespace..."; \
	oc project $$CONFIG_NAMESPACE 2>/dev/null || oc new-project $$CONFIG_NAMESPACE || (echo "Error: Cannot create/switch to namespace '$$CONFIG_NAMESPACE'." && mv deployment/mpp/tenant.yaml.bak deployment/mpp/tenant.yaml 2>/dev/null && exit 1); \
	echo "Applying TenantNamespace CR to create runtime namespace..."; \
	oc apply -f deployment/mpp/tenant.yaml || (mv deployment/mpp/tenant.yaml.bak deployment/mpp/tenant.yaml 2>/dev/null && exit 1); \
	echo "Waiting for runtime namespace '$$RUNTIME_NAMESPACE' to be created..."; \
	COUNTER=1; \
	until oc get project $$RUNTIME_NAMESPACE 2>/dev/null || [ $$COUNTER -gt 30 ]; do \
		echo "Waiting for namespace... ($$COUNTER/30)"; \
		sleep 2; \
		COUNTER=$$((COUNTER + 1)); \
	done; \
	if [ $$COUNTER -le 30 ]; then \
		echo "Runtime namespace '$$RUNTIME_NAMESPACE' is ready"; \
	fi; \
	oc project "$(TENANT)--$(RUNTIME_NAMESPACE)" > /dev/null 2>&1 || (echo "Error: Runtime namespace '$$RUNTIME_NAMESPACE' was not created" && mv deployment/mpp/tenant.yaml.bak deployment/mpp/tenant.yaml 2>/dev/null && exit 1); \
	echo "Switching to runtime namespace..."; \
	oc project $$RUNTIME_NAMESPACE || (echo "Error: Cannot switch to runtime namespace '$$RUNTIME_NAMESPACE'" && mv deployment/mpp/tenant.yaml.bak deployment/mpp/tenant.yaml 2>/dev/null && exit 1); \
	echo "Creating BuildConfig and ImageStream..."; \
	oc apply -f deployment/mpp/buildconfig.yaml; \
	oc apply -f deployment/mpp/imagestream.yaml; \
	echo "Building container image from source..."; \
	oc start-build agent --from-dir=. \
		--exclude='(^|/)\.venv(/|$$)' \
		--exclude='(^|/)__pycache__(/|$$)' \
		--exclude='(^|/)\.pytest_cache(/|$$)' \
		--exclude='(^|/)tests(/|$$)' \
		--exclude='(^|/)examples(/|$$)' \
		--exclude='(^|/)\.mypy_cache(/|$$)' \
		--exclude='(^|/)\.ruff_cache(/|$$)' \
		--exclude='.*\.log$$' \
		--follow || (mv deployment/mpp/tenant.yaml.bak deployment/mpp/tenant.yaml 2>/dev/null; exit 1); \
	echo "Deploying resources to MPP..."; \
	oc apply -k deployment/mpp/ || (mv deployment/mpp/tenant.yaml.bak deployment/mpp/tenant.yaml 2>/dev/null; exit 1); \
	rm -f deployment/mpp/tenant.yaml.bak; \
	echo "Deployment complete!"; \
	echo "Checking deployment status..."; \
	oc get pods -l app=agent; \
	echo ""; \
	echo "Useful commands:"; \
	echo "  View logs: oc logs -l app=agent --tail=100"; \
	echo "  Get route: oc get route agent"; \
	echo "  Check status: oc get pods,svc,route -l app=agent"

undeploy:
	@if [ "$(filter openshift,$(MAKECMDGOALS))" = "openshift" ]; then \
		echo "Checking for oc CLI..."; \
		which oc > /dev/null || (echo "Error: oc CLI not found. Please install OpenShift CLI." && exit 1); \
		oc project $(NAMESPACE) || (echo "Error: Cannot switch to namespace '$(NAMESPACE)'" && exit 1); \
		echo "Removing OpenShift deployment..."; \
		oc delete deployment,service,route,configmap,secret,pvc,buildconfig,imagestream -l app=agent 2>/dev/null || true; \
		echo "Undeployment complete!"; \
		exit 1; \
	elif [ "$(filter mpp,$(MAKECMDGOALS))" = "mpp" ]; then \
		echo "Checking for oc CLI..."; \
		RUNTIME_NAMESPACE="$(TENANT)--template"; \
		which oc > /dev/null || (echo "Error: oc CLI not found. Please install OpenShift CLI." && exit 1); \
		oc project $$RUNTIME_NAMESPACE || (echo "Error: Cannot switch to runtime namespace '$$RUNTIME_NAMESPACE'" && exit 1); \
		echo "Removing MPP deployment..."; \
		oc delete deployment,service,route,configmap,secret,pvc,buildconfig,imagestream -l app=agent 2>/dev/null || true; \
		echo "Undeployment complete!"; \
		exit 1; \
	else \
		echo "Usage: make undeploy [openshift|mpp]"; \
		echo "Available undeployment targets: openshift, mpp"; \
		exit 1; \
	fi

%:
	@:
