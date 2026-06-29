import json
import boto3
import os

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

class InvalidDataException(Exception): pass

def lambda_handler(event, context):
    bucket = event['detail']['bucket']['name']
    key = event['detail']['object']['key']

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
    except json.JSONDecodeError:
        raise InvalidDataException("Malformed JSON")
    except Exception as e:
        if 'timeout' in key.lower():
            raise RuntimeError("Transient NetworkException")
        raise e

    if 'id' not in data:
        raise InvalidDataException("Missing 'id'")

    table = dynamodb.Table('ProcessedData')
    table.put_item(Item={'id': str(data['id']), 'payload': data})

    return {"status": "success", "id": data['id']}
