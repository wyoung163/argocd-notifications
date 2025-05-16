import subprocess
import sys
import os
import tempfile
import yaml

NAMESPACE = "argocd"
SECRET_NAME = "argocd-notifications-secret"
CONTROLLER_NAME = "argocd-notifications-controller"

def run(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)
    
def apply_argocd_notifications():
    run("kubectl apply -f https://raw.githubusercontent.com/argoproj-labs/argocd-notifications/release-1.0/manifests/install.yaml -n argocd")
    run("kubectl apply -f https://raw.githubusercontent.com/argoproj-labs/argocd-notifications/release-1.0/catalog/install.yaml -n argocd")

def create_slack_cm():
    script_dir = os.path.dirname(os.path.abspath(__file__))  
    file_path = os.path.join(script_dir, "argocd-notifications-cm.yaml")
    file_name = "argocd-notifications-cm.yaml"

    if not os.path.exists(file_path):
        print(f"파일을 찾을 수 없습니다: {file_path}")
        sys.exit(1)
    run(f"kubectl apply -f {file_name} -n {NAMESPACE}")

def create_slack_secret(slack_token):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "argocd-notifications-secret.yaml")
    file_name = "argocd-notifications-secret.yaml"

    if not os.path.exists(file_path):
        print(f"파일이 존재하지 않습니다: {file_path}")
        sys.exit(1)

    # 파일 열기 및 내용 로드
    with open(file_path, "r") as f:
        secret = yaml.safe_load(f)

    # stringData.slack-token 값만 변경
    if "stringData" not in secret:
        secret["stringData"] = {}

    secret["stringData"]["slack-token"] = slack_token

    # 다시 저장
    with open(file_path, "w") as f:
        yaml.dump(secret, f)

    # 적용
    run(f"kubectl apply -f {file_name}")
    print(f"✅ Slack 토큰을 secret.yaml에 반영하고 적용했습니다.")


def patch_controller_for_secret_volume():
    patch = {
        "spec": {
            "template": {
                "spec": {
                    "volumes": [
                        {
                            "name": "slack-token-volume",
                            "secret": {
                                "secretName": SECRET_NAME,
                                "items": [
                                    {
                                        "key": "slack-token",
                                        "path": "slack-token.txt"
                                    }
                                ]
                            }
                        }
                    ],
                    "containers": [
                        {
                            "name": CONTROLLER_NAME,
                            "volumeMounts": [
                                {
                                    "name": "slack-token-volume",
                                    "mountPath": "/etc/slack",
                                    "readOnly": True
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        yaml.dump(patch, f)
        f.flush()
        run(f"kubectl -n argocd patch deployment {CONTROLLER_NAME} --patch-file {f.name}")
        os.unlink(f.name)

def main():
    if len(sys.argv) != 2:
        print("python setup_argocd_notifications.py <SLACK_TOKEN> 형태로 명령어를 입력해주세요.")
        sys.exit(1)

    slack_token = sys.argv[1]
    
    print("Argo CD Notifications 구축")
    apply_argocd_notifications()

    print("Argo CD Notifications 설정")
    # Secret 및 CM YAML 파일 적용
    create_slack_secret(slack_token)
    create_slack_cm()
    # Controller에 Slack Secret 마운트 Patch
    patch_controller_for_secret_volume()

    print("✅ 완료되었습니다! Slack 알림 구성이 완료되었습니다.")

if __name__ == "__main__":
    main()

