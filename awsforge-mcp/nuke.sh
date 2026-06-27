#!/bin/bash
# AWSForge MCP - Nuclear Kill Switch

set -euo pipefail

DRY_RUN=false
FORCE=false
START_TIME=$(date +%s)
LOG_FILE="/opt/awsforge/logs/nuke_$(date +%Y%m%d_%H%M%S).log"

mkdir -p /opt/awsforge/logs

for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --force) FORCE=true ;;
    esac
done

echo -e "\e[31m"
echo "==========================================================="
echo "☢️  NUCLEAR KILL SWITCH ENGAGED - AWSFORGE MCP"
echo "==========================================================="
echo -e "\e[0m"

if [ "$DRY_RUN" = true ]; then
    echo "⚠️  DRY RUN MODE: Resources will only be listed, not destroyed."
else
    echo "⚠️  WARNING: This will destroy ALL AWS resources created by AWSForge."
    if [ "$FORCE" = false ]; then
        read -p "Type 'DESTROY' to proceed: " CONFIRM
        if [ "$CONFIRM" != "DESTROY" ]; then
            echo "Aborted."
            exit 1
        fi
    fi
fi

exec > >(tee -a "$LOG_FILE") 2>&1

echo "[Phase 1] Destroying Terraform Workspaces..."
WS_COUNT=0
WS_FAILED=0

if [ -d "/opt/awsforge/workspaces" ]; then
    for ws in /opt/awsforge/workspaces/*; do
        if [ -d "$ws" ] && [ -f "$ws/main.tf" ]; then
            WS_COUNT=$((WS_COUNT+1))
            echo "-> Destroying workspace: $(basename "$ws")"
            if [ "$DRY_RUN" = false ]; then
                cd "$ws"
                if terraform destroy -auto-approve -no-color; then
                    cd /opt/awsforge
                    rm -rf "$ws"
                else
                    echo "❌ Failed to destroy workspace: $(basename "$ws")"
                    WS_FAILED=$((WS_FAILED+1))
                    cd /opt/awsforge
                fi
            fi
        fi
    done
fi

echo "[Phase 2] Sweeping orphaned resources via AWS CLI (Tag: ManagedBy=AWSForge)..."
REGION=${AWS_REGION:-ap-south-1}
RESOURCES=$(aws resourcegroupstaggingapi get-resources --region $REGION --tag-filters Key=ManagedBy,Values=AWSForge --output json)

S3_COUNT=0
LAMBDA_COUNT=0
SNS_COUNT=0
SQS_COUNT=0
ROLE_COUNT=0

if [ "$DRY_RUN" = true ]; then
    echo "The following ARNs would be destroyed:"
    echo "$RESOURCES" | jq -r '.ResourceTagMappingList[].ResourceARN' || echo "None found."
else
    for arn in $(echo "$RESOURCES" | jq -r '.ResourceTagMappingList[].ResourceARN'); do
        service=$(echo "$arn" | cut -d':' -f3)
        echo "Found resource: $arn"
        
        case $service in
            s3)
                bucket=$(echo "$arn" | cut -d':' -f6)
                echo "-> Emptying and deleting S3 bucket: $bucket"
                aws s3api delete-objects --region $REGION --bucket $bucket --delete "$(aws s3api list-object-versions --region $REGION --bucket $bucket --query='{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --max-items 1000)" 2>/dev/null || true
                aws s3api delete-objects --region $REGION --bucket $bucket --delete "$(aws s3api list-object-versions --region $REGION --bucket $bucket --query='{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --max-items 1000)" 2>/dev/null || true
                aws s3api delete-bucket --region $REGION --bucket $bucket || true
                S3_COUNT=$((S3_COUNT+1))
                ;;
            lambda)
                func=$(echo "$arn" | cut -d':' -f7)
                echo "-> Deleting Lambda function: $func"
                aws lambda delete-function --region $REGION --function-name "$func" || true
                LAMBDA_COUNT=$((LAMBDA_COUNT+1))
                ;;
            sns)
                echo "-> Deleting SNS topic: $arn"
                aws sns delete-topic --region $REGION --topic-arn "$arn" || true
                SNS_COUNT=$((SNS_COUNT+1))
                ;;
            sqs)
                # SQS needs URL, not ARN
                queue_name=$(echo "$arn" | cut -d':' -f6)
                account_id=$(echo "$arn" | cut -d':' -f5)
                queue_url="https://sqs.${REGION}.amazonaws.com/${account_id}/${queue_name}"
                echo "-> Deleting SQS queue: $queue_name"
                aws sqs delete-queue --region $REGION --queue-url "$queue_url" || true
                SQS_COUNT=$((SQS_COUNT+1))
                ;;
            iam)
                role_name=$(echo "$arn" | cut -d'/' -f2)
                echo "-> Detaching policies and deleting IAM role: $role_name"
                for pol in $(aws iam list-attached-role-policies --role-name "$role_name" --query 'AttachedPolicies[].PolicyArn' --output text); do
                    aws iam detach-role-policy --role-name "$role_name" --policy-arn "$pol" || true
                done
                for ipol in $(aws iam list-role-policies --role-name "$role_name" --query 'PolicyNames[]' --output text); do
                    aws iam delete-role-policy --role-name "$role_name" --policy-name "$ipol" || true
                done
                aws iam delete-role --role-name "$role_name" || true
                ROLE_COUNT=$((ROLE_COUNT+1))
                ;;
            *)
                echo "-> Skipping automatic sweep for unhandled service type: $service (Please delete manually)"
                ;;
        esac
    done
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "==========================================================="
echo "📊 NUKE REPORT"
echo "Time Taken: ${ELAPSED} seconds"
echo "Workspaces Destroyed: $WS_COUNT (Failed: $WS_FAILED)"
echo "Orphaned Resources Swept:"
echo " - S3 Buckets: $S3_COUNT"
echo " - Lambda Functions: $LAMBDA_COUNT"
echo " - SNS Topics: $SNS_COUNT"
echo " - SQS Queues: $SQS_COUNT"
echo " - IAM Roles: $ROLE_COUNT"
echo "==========================================================="
echo "⚠️  Reminder: Please verify in AWS Console -> Resource Groups -> Tag Editor (Filter: ManagedBy=AWSForge)"
