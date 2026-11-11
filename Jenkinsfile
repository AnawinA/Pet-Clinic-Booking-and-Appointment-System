pipeline {
    agent any

    triggers {
        githubPush()
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
        skipDefaultCheckout()
    }

    environment {
        COMPOSE_PROJECT_NAME = 'petcare-ci'
        REMOTE_DIR           = '/root/Pet-Clinic-Booking-and-Appointment-System'
        AUTH_DIR             = "/root/.docker/petcare-${BUILD_NUMBER}"
        SSH_DEVTOOLS         = 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@devtools'
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
                script {
                    env.COMMIT_TAG = sh(
                        returnStdout: true,
                        script: 'git rev-parse --short=12 HEAD'
                    ).trim()
                    env.IMAGE_TAG = env.COMMIT_TAG
                }
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'HUB_USER',
                    passwordVariable: 'HUB_TOKEN'
                )]) {
                    script {
                        env.DOCKERHUB_NAMESPACE = env.HUB_USER
                        if (!(env.DOCKERHUB_NAMESPACE ==~ /[a-z0-9]+(?:[._-][a-z0-9]+)*/)) {
                            error 'The Docker Hub username is not a valid image namespace.'
                        }
                    }
                }
                script {
                    def dotenvLine = { key, value ->
                        def text = value.toString()
                        if (text.contains('\n') || text.contains('\r')) {
                            error "Jenkins value for ${key} cannot contain a newline."
                        }
                        "${key}='${text.replace("\\", "\\\\").replace("'", "\\'")}'"
                    }
                    def composeEnv = [
                        ['COMPOSE_PROJECT_NAME', env.COMPOSE_PROJECT_NAME],
                        ['POSTGRES_USER', env.POSTGRES_USER],
                        ['POSTGRES_PASSWORD', env.POSTGRES_PASSWORD],
                        ['POSTGRES_DB', env.POSTGRES_DB],
                        ['JWT_SECRET', env.JWT_SECRET],
                        ['ACCESS_TOKEN_MINUTES', '60'],
                        ['CORS_ORIGINS', 'http://localhost'],
                        ['WORKER_POLL_SECONDS', '5'],
                        ['ENVIRONMENT', 'production'],
                        ['PHOTO_DIR', '/data/pet-photos'],
                        ['GRAFANA_ADMIN_USER', env.GRAFANA_ADMIN_USER],
                        ['GRAFANA_ADMIN_PASSWORD', env.GRAFANA_ADMIN_PASSWORD],
                        ['DOCKERHUB_NAMESPACE', env.DOCKERHUB_NAMESPACE],
                        ['IMAGE_TAG', env.IMAGE_TAG]
                    ].collect { entry -> dotenvLine(entry[0], entry[1]) }.join('\n') + '\n'
                    if (!(env.POSTGRES_PASSWORD ==~ /[A-Za-z0-9._~-]+/)) {
                        error 'The PostgreSQL password must use URL-safe characters for the database connection URL.'
                    }
                    def testDatabaseUrl = "postgresql+asyncpg://${env.POSTGRES_USER}:${env.POSTGRES_PASSWORD}@postgres:5432/petcare_test"
                    writeFile file: '.jenkins-compose.env', text: composeEnv
                    writeFile file: '.jenkins-test.env', text: [
                        dotenvLine('TEST_DATABASE_URL', testDatabaseUrl),
                        dotenvLine('DATABASE_URL', testDatabaseUrl)
                    ].join('\n') + '\n'
                }
                sh 'chmod 600 .jenkins-compose.env .jenkins-test.env'
                echo "Building commit ${env.COMMIT_TAG}"
            }
        }

        stage('Connect and Sync to devtools') {
            steps {
                sshagent(credentials: ['devtools-ssh']) {
                    sh '''
                        set -e
                        $SSH_DEVTOOLS "hostname && whoami && docker --version && docker compose version"
                        chmod 600 .jenkins-compose.env .jenkins-test.env
                        $SSH_DEVTOOLS "mkdir -p '$REMOTE_DIR'"
                        tar --exclude=.git --exclude=.env --exclude='.env.*' --exclude=.jenkins-* --exclude=node_modules --exclude=dist -cf - . | $SSH_DEVTOOLS "tar -xf - -C '$REMOTE_DIR'"
                        $SSH_DEVTOOLS "test -f '$REMOTE_DIR/docker-compose.yml' && test -f '$REMOTE_DIR/Jenkinsfile'"
                        $SSH_DEVTOOLS "umask 077; cat > '$REMOTE_DIR/.env'" < .jenkins-compose.env
                        $SSH_DEVTOOLS "chmod 600 '$REMOTE_DIR/.env'"
                        $SSH_DEVTOOLS "umask 077; cat > '$REMOTE_DIR/.jenkins-test.env'" < .jenkins-test.env
                        $SSH_DEVTOOLS "chmod 600 '$REMOTE_DIR/.jenkins-test.env'"
                    '''
                }
            }
        }

        stage('Build & Verify') {
            steps {
                sshagent(credentials: ['devtools-ssh']) {
                    sh '''
                        $SSH_DEVTOOLS "cd '$REMOTE_DIR' && bash -se" <<'REMOTE'
                        set -e
                        docker compose build
                        docker compose up -d postgres
                        for i in $(seq 1 60); do
                            if docker compose exec -T postgres pg_isready -U petcare -d petcare >/dev/null 2>&1; then break; fi
                            sleep 1
                        done
                        docker compose exec -T postgres pg_isready -U petcare -d petcare
                        EXISTS=$(docker compose exec -T postgres psql -U petcare -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='petcare_test'")
                        if [ "$EXISTS" != "1" ]; then docker compose exec -T postgres createdb -U petcare petcare_test; fi
                        docker compose run --rm --env-from-file .jenkins-test.env web1 sh -c "ruff check app tests && mypy app && alembic upgrade head && pytest -q"
                        docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.21.2 detect --source=/repo --config=/repo/.gitleaks.toml --no-git --exit-code 1 --redact
                    REMOTE
                    '''.stripIndent()
                }
            }
        }

        stage('Publish to Docker Hub') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKERHUB_USER',
                    passwordVariable: 'DOCKERHUB_TOKEN'
                )]) {
                    sshagent(credentials: ['devtools-ssh']) {
                        sh '''
                            set +x
                            printf '%s' "$DOCKERHUB_TOKEN" | $SSH_DEVTOOLS "umask 077; mkdir -p '$AUTH_DIR'; docker --config '$AUTH_DIR' login --username '$DOCKERHUB_USER' --password-stdin"
                            $SSH_DEVTOOLS "cd '$REMOTE_DIR' && DOCKER_CONFIG='$AUTH_DIR' docker compose push web1 nginx"
                            $SSH_DEVTOOLS "AUTH_DIR='$AUTH_DIR' HUB_USER='$DOCKERHUB_USER' COMMIT_TAG='$COMMIT_TAG' BUILD_NUMBER='$BUILD_NUMBER' bash -se" <<'REMOTE'
                            for image in petcare-backend petcare-nginx; do
                                docker --config "$AUTH_DIR" tag "$HUB_USER/$image:$COMMIT_TAG" "$HUB_USER/$image:build-$BUILD_NUMBER"
                                docker --config "$AUTH_DIR" push "$HUB_USER/$image:build-$BUILD_NUMBER"
                            done
                            REMOTE
                        '''.stripIndent()
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                sshagent(credentials: ['devtools-ssh']) {
                    sh '''
                        $SSH_DEVTOOLS "cd '$REMOTE_DIR' && DOCKER_CONFIG='$AUTH_DIR' docker compose pull web1 nginx && DOCKER_CONFIG='$AUTH_DIR' docker compose up -d --no-build --remove-orphans"
                    '''
                }
            }
        }

        stage('Post-Deployment Verification') {
            steps {
                sshagent(credentials: ['devtools-ssh']) {
                    sh '''
                    $SSH_DEVTOOLS "cd '$REMOTE_DIR' && bash -se" <<'REMOTE'
                    set -e
                    docker compose run --rm web1 python -m scripts.seed
                    BASE_URL=http://localhost bash scripts/post_deploy_check.sh
                    REMOTE
                    '''.stripIndent()
                }
            }
            post {
                failure {
                    echo 'Post-deployment verification failed on devtools: investigate remote Compose status/logs and roll back to the previous image tag if needed.'
                }
            }
        }
    }

    post {
        always {
            sshagent(credentials: ['devtools-ssh']) {
                sh '''
                    $SSH_DEVTOOLS "cd '$REMOTE_DIR' && docker compose ps" || true
                    $SSH_DEVTOOLS "cd '$REMOTE_DIR' && docker compose logs --tail=80 web1 web2 worker nginx" || true
                    $SSH_DEVTOOLS "docker --config '$AUTH_DIR' logout || true; rm -rf '$AUTH_DIR'; rm -f '$REMOTE_DIR/.jenkins-test.env'" || true
                '''
            }
            sh 'rm -f .jenkins-compose.env .jenkins-test.env'
        }
        failure {
            echo 'Pipeline failed. See docs/runbook.md for recovery steps.'
        }
    }
}
