import boto3
import json
import os

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

def lambda_handler(event, context):
    bucket = event['bucket']
    key = event['key']
    
    # Defensive check: Do not re-quarantine if it's already there
    if key.startswith('quarantine/'):
        return {"status": "already_quarantined"}

    error = event.get('error', 'Unknown Error')
    new_key = key.replace('inbound/', 'quarantine/')

    # Move to quarantine
    s3_client.copy_object(
        Bucket=bucket, 
        CopySource={'Bucket': bucket, 'Key': key}, 
        Key=new_key
    )
    s3_client.delete_object(Bucket=bucket, Key=key)

    # Send alert to SQS
    queue_url = os.environ['SQS_QUEUE_URL']
    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            'bucket': bucket, 
            'bad_file': key, 
            'quarantined_file': new_key,
            'error': error
        })
    )
    return {"status": "quarantined"}
