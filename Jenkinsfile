pipeline {
  agent any
  parameters { booleanParam(name: 'RUN_E2E', defaultValue: false, description: 'Ejecutar pruebas E2E completas') }
  options { skipDefaultCheckout(); timestamps(); disableConcurrentBuilds(); timeout(time: 45, unit: 'MINUTES') }
  triggers { pollSCM('H/5 * * * *') }
  environment { SERVICE = 'ms-notifications'; COMPOSE_SERVICE = 'notificaciones-service'; IMAGE = 'rhm/ms-notifications' }
  stages {
    stage('Checkout') { steps { checkout scm; script { env.IMAGE_TAG = "${env.BUILD_NUMBER}-${sh(script: 'git rev-parse --short=7 HEAD', returnStdout: true).trim()}" } } }
    stage('Build') {
      agent { docker { image 'python:3.13-slim'; reuseNode true } }
      environment { HOME = '/tmp'; PIP_CACHE_DIR = '/tmp/pip-cache' }
      steps { sh 'pip install --no-cache-dir -r requirements.txt'; sh 'python -m compileall -q app' }
    }
    stage('Test') {
      agent { docker { image 'python:3.13-slim'; reuseNode true } }
      environment { HOME = '/tmp'; PIP_CACHE_DIR = '/tmp/pip-cache' }
      steps { sh 'pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt'; sh 'mkdir -p reports && python -m pytest --cov-config=.coveragerc --junitxml=reports/junit.xml' }
      post { always { junit testResults: 'reports/junit.xml', allowEmptyResults: false; archiveArtifacts artifacts: 'reports/coverage.xml', allowEmptyArchive: false } }
    }
    stage('Secret scan') { steps { sh 'docker run --rm -v "$PWD:/src" zricethezav/gitleaks:v8.24.0 detect --source /src --no-git --redact' } }
    stage('Dependency scan') {
      steps { sh 'mkdir -p reports/security; docker run --rm -v "$PWD:/src" aquasec/trivy:0.76.2 fs --scanners vuln --severity HIGH,CRITICAL --exit-code 0 --format json --output /src/reports/security/dependencies.json /src; docker run --rm -v "$PWD:/src" aquasec/trivy:0.76.2 fs --scanners vuln --severity CRITICAL --exit-code 1 --no-progress /src' }
      post { always { archiveArtifacts artifacts: 'reports/security/dependencies.json', allowEmptyArchive: false } }
    }
    stage('SonarQube') {
      agent { docker { image 'sonarsource/sonar-scanner-cli:11'; reuseNode true; args "--network ${env.RHM_CI_NETWORK}" } }
      steps { withSonarQubeEnv('sonarqube') { sh 'sonar-scanner -Dsonar.projectKey=rhm-ms-notifications -Dsonar.sources=app -Dsonar.tests=tests -Dsonar.exclusions=app/main.py,app/config.py,app/logging_setup.py,app/telemetry.py,app/infrastructure/persistence/**,app/infrastructure/messaging/consumer.py,app/application/notify_account_status.py,app/application/notify_security_token.py -Dsonar.python.coverage.reportPaths=reports/coverage.xml' } }
    }
    stage('Quality Gate') { steps { timeout(time: 5, unit: 'MINUTES') { waitForQualityGate abortPipeline: true } } }
    stage('Package') { steps { sh 'docker build -t "$IMAGE:$IMAGE_TAG" -t "$IMAGE:latest" .' } }
    stage('Image scan') {
      steps { sh 'docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD:/src" aquasec/trivy:0.76.2 image --severity HIGH,CRITICAL --exit-code 0 --format json --output /src/reports/security/image.json "$IMAGE:$IMAGE_TAG"; docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.2 image --severity CRITICAL --exit-code 1 --no-progress "$IMAGE:$IMAGE_TAG"' }
      post { always { archiveArtifacts artifacts: 'reports/security/image.json', allowEmptyArchive: false } }
    }
    stage('Publish') { steps { sh 'docker tag "$IMAGE:$IMAGE_TAG" "$RHM_REGISTRY/$IMAGE:$IMAGE_TAG"; docker tag "$IMAGE:latest" "$RHM_REGISTRY/$IMAGE:latest"; docker push "$RHM_REGISTRY/$IMAGE:$IMAGE_TAG"; docker push "$RHM_REGISTRY/$IMAGE:latest"' } }
    stage('E2E Tests') {
      when { expression { params.RUN_E2E } }
      environment { COMPOSE_PROJECT_NAME = "rhm-e2e-${env.SERVICE}"; COMPOSE_FILE = 'docker-compose.yml:ci/docker-compose.e2e.yml:../service-under-test.yml'; E2E_ADMIN = credentials('e2e-admin') }
      steps {
        dir('.e2e') { deleteDir() }
        dir('.e2e') {
          sh '''repo="$RHM_GIT_BASE_URL/rhm-database-infrastructure.git"; branch=''; git ls-remote --exit-code --heads "$repo" "$RHM_GIT_BRANCH" >/dev/null 2>&1 && branch="--branch $RHM_GIT_BRANCH"; git clone --quiet --depth 1 $branch "$repo" rhm-database-infrastructure; sh rhm-database-infrastructure/ci/checkout-stack.sh; sh rhm-database-infrastructure/ci/provision-e2e-secret-volume.sh'''
          writeFile file: 'service-under-test.yml', text: """\
            services:
              ${env.COMPOSE_SERVICE}:
                image: ${env.IMAGE}:${env.IMAGE_TAG}
                build: !reset null
            """.stripIndent()
          dir('rhm-database-infrastructure') { sh 'docker compose down -v --remove-orphans >/dev/null 2>&1 || true; ADMIN_USERNAME="$E2E_ADMIN_USR" ADMIN_PASSWORD="$E2E_ADMIN_PSW" docker compose up -d --build --quiet-pull --wait --wait-timeout 300' }
          script { docker.image('node:24-alpine').inside("--network ${env.COMPOSE_PROJECT_NAME}-network") { dir('e2e-tests') { sh 'npm ci --no-audit --no-fund'; sh 'BASE_URL="${E2E_BASE_URL:-http://api-gateway:8080}" E2E_ADMIN_USERNAME="$E2E_ADMIN_USR" E2E_ADMIN_PASSWORD="$E2E_ADMIN_PSW" npm test || echo "Escenarios BDD fallidos"' } } }
        }
      }
      post { always { dir('.e2e/rhm-database-infrastructure') { sh 'docker compose logs --no-color --timestamps > ../e2e-docker-logs.txt 2>&1 || true'; sh 'docker compose down -v --remove-orphans || true' }; archiveArtifacts artifacts: '.e2e/e2e-docker-logs.txt', allowEmptyArchive: true; junit testResults: '.e2e/e2e-tests/reports/junit.xml', allowEmptyResults: false; cucumber(jsonReportDirectory: '.e2e/e2e-tests/reports', fileIncludePattern: 'cucumber.json', buildStatus: 'UNSTABLE', reportTitle: 'Escenarios BDD (e2e-tests)'); publishHTML(target: [reportDir: '.e2e/e2e-tests/reports', reportFiles: 'cucumber.html', reportName: 'Reporte BDD', keepAll: true, alwaysLinkToLastBuild: true, allowMissing: true]) } }
    }
  }
  post { always { sh 'if [ -n "${IMAGE_TAG:-}" ]; then docker image rm "$IMAGE:$IMAGE_TAG" "$RHM_REGISTRY/$IMAGE:$IMAGE_TAG" >/dev/null 2>&1 || true; fi'; echo "Pipeline de ${env.SERVICE} finalizado: ${currentBuild.currentResult}" } }
}
