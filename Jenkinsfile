pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        COMPOSE_PROJECT_NAME = 'petcare-ci'
        POSTGRES_USER        = 'petcare'
        POSTGRES_DB          = 'petcare'
        GRAFANA_ADMIN_USER   = 'admin'
        JWT_SECRET           = credentials('petcare-jwt-secret')
        POSTGRES_PASSWORD    = credentials('petcare-postgres-password')
        GRAFANA_ADMIN_PASSWORD = credentials('petcare-grafana-password')
        TEST_DATABASE_URL    = 'postgresql+asyncpg://petcare:petcare-ci@postgres:5432/petcare_test'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git rev-parse --short HEAD'
            }
        }

        stage('Build & Verify') {
            steps {
                sh 'docker compose build'
                sh 'docker compose up -d postgres'
                sh '''
                    set -e
                    for i in $(seq 1 60); do
                        if docker compose exec -T postgres pg_isready -U petcare -d petcare >/dev/null 2>&1; then break; fi
                        sleep 1
                    done
                    docker compose exec -T postgres pg_isready -U petcare -d petcare
                '''
                sh '''
                    set -e
                    EXISTS=$(docker compose exec -T postgres psql -U petcare -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='petcare_test'")
                    if [ "$EXISTS" != "1" ]; then docker compose exec -T postgres createdb -U petcare petcare_test; fi
                '''
                sh '''
                    docker compose run --rm \
                        -e TEST_DATABASE_URL="${TEST_DATABASE_URL}" \
                        -e DATABASE_URL="${TEST_DATABASE_URL}" \
                        web1 sh -c "ruff check app tests && mypy app && alembic upgrade head && pytest -q"
                '''
                sh 'docker build -f nginx/Dockerfile -t petcare-nginx:ci .'
                sh '''
                    docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.21.2 \
                        detect --source=/repo --config=/repo/.gitleaks.toml \
                        --no-git --exit-code 1 --redact
                '''
            }
        }

        stage('Deploy') {
            steps {
                sh 'docker compose up -d --remove-orphans'
            }
        }

        stage('Post-Deployment Verification') {
            steps {
                sh '''
                    set -e
                    docker compose run --rm web1 python -m scripts.seed
                    BASE_URL=http://localhost bash scripts/post_deploy_check.sh
                '''
            }
            post {
                failure {
                    echo 'Post-deployment verification failed: investigate "docker compose ps" / logs and roll back to the previous image tag if needed.'
                }
            }
        }
    }

    post {
        always {
            sh 'docker compose ps || true'
            sh 'docker compose logs --tail=80 web1 web2 worker nginx || true'
        }
        failure {
            echo 'Pipeline failed. See docs/runbook.md for recovery steps.'
        }
    }
}
