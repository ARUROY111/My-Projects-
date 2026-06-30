import json
import boto3
import os
import urllib.parse

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

class InvalidDataException(Exception): pass

def lambda_handler(event, context):
    bucket = event['detail']['bucket']['name']
    key = urllib.parse.unquote_plus(event['detail']['object']['key'])
    
    # Defensive check: Ignore files already in quarantine
    if key.startswith('quarantine/'):
        print(f"Ignoring file already in quarantine: {key}")
        return {"status": "ignored", "reason": "already quarantined"}

    print(f"Processing Key: {key} from Bucket: {bucket}")

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
    except json.JSONDecodeError:
        raise InvalidDataException("Malformed JSON")
    except Exception as e:
        # Simulate transient error for testing
        if 'timeout' in key.lower():
            raise RuntimeError("Transient NetworkException")
        raise e

    if 'id' not in data:
        raise InvalidDataException("Missing 'id'")

    table = dynamodb.Table('ProcessedData')
    table.put_item(Item={'id': str(data['id']), 'payload': data})

    return {"status": "success", "id": data['id']}
