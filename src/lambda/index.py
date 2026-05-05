# src/lambda/index.py - S3 Event Trigger Lambda

import os
import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
AUDIT_TABLE_NAME = os.environ['AUDIT_TABLE_NAME']
ECS_CLUSTER = os.environ['ECS_CLUSTER']
ECS_TASK_DEFINITION = os.environ['ECS_TASK_DEFINITION']
ECS_SUBNETS = os.environ.get('ECS_SUBNETS', '').split(',')
ECS_SECURITY_GROUP = os.environ.get('ECS_SECURITY_GROUP', '')
AWS_REGION = os.environ['AWS_REGION']
KMS_KEY_ID = os.environ['KMS_KEY_ID']

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
ecs_client = boto3.client('ecs')
table = dynamodb.Table(AUDIT_TABLE_NAME)

def write_audit_record(organization_id: str, file_key: str, status: str, 
                       step: str, details: Dict[str, Any]) -> None:
    """Write audit record to DynamoDB with proper indexing."""
    timestamp = datetime.utcnow().isoformat()
    record = {
        'PK': f"FILE#{file_key}",
        'SK': f"{timestamp}#{step}",
        'OrganizationId': organization_id,
        'FileKey': file_key,
        'Status': status,
        'Step': step,
        'EventTimestamp': timestamp,
        'Details': json.dumps(details)
    }
    
    try:
        table.put_item(Item=record)
        logger.info(f"Audit record written: {organization_id}/{file_key} - {step}")
    except Exception as e:
        logger.error(f"Failed to write audit record: {str(e)}")
        raise

def validate_file(bucket: str, key: str) -> tuple[bool, str, Dict[str, Any]]:
    """Validate the uploaded file for organization-id tag and basic requirements."""
    try:
        # Get object tags
        tagging = s3_client.get_object_tagging(Bucket=bucket, Key=key)
        tags = {tag['Key']: tag['Value'] for tag in tagging['TagSet']}
        
        organization_id = tags.get('organization-id')
        if not organization_id:
            return False, "Missing required tag: organization-id", {}
        
        # Validate organization-id format (simple alphanumeric + hyphen)
        import re
        if not re.match(r'^[a-zA-Z0-9\-]{3,50}$', organization_id):
            return False, "Invalid organization-id format", {}
        
        # Get object metadata
        head = s3_client.head_object(Bucket=bucket, Key=key)
        file_size = head['ContentLength']
        
        # Basic metadata validation
        if file_size == 0:
            return False, "Empty file not allowed", {}
        
        if file_size > 500 * 1024 * 1024:  # 500MB limit
            return False, "File exceeds maximum size (500MB)", {}
        
        metadata = {
            'size_bytes': file_size,
            'last_modified': head['LastModified'].isoformat(),
            'etag': head['ETag'].strip('"')
        }
        
        return True, organization_id, metadata
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return False, f"Validation error: {str(e)}", {}

def trigger_ecs_task(bucket: str, key: str, organization_id: str, metadata: Dict[str, Any]) -> bool:
    """Trigger ECS Fargate task to process the file."""
    try:
        # Prepare overrides with file information
        overrides = {
            'containerOverrides': [
                {
                    'name': 'processor',
                    'environment': [
                        {'name': 'FILE_BUCKET', 'value': bucket},
                        {'name': 'FILE_KEY', 'value': key},
                        {'name': 'ORGANIZATION_ID', 'value': organization_id},
                        {'name': 'FILE_SIZE', 'value': str(metadata['size_bytes'])},
                        {'name': 'FILE_ETAG', 'value': metadata['etag']}
                    ]
                }
            ]
        }
        
        # Run ECS task
        response = ecs_client.run_task(
            cluster=ECS_CLUSTER,
            taskDefinition=ECS_TASK_DEFINITION,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': ECS_SUBNETS,
                    'securityGroups': [ECS_SECURITY_GROUP],
                    'assignPublicIp': 'ENABLED' if not ECS_SUBNETS else 'DISABLED'
                }
            },
            overrides=overrides,
            propagateTags='TASK_DEFINITION'
        )
        
        if response['failures']:
            logger.error(f"ECS task failures: {response['failures']}")
            return False
        
        task_arn = response['tasks'][0]['taskArn']
        logger.info(f"Started ECS task: {task_arn}")
        
        # Write task ARN to audit (will be updated by ECS task itself)
        return True
        
    except Exception as e:
        logger.error(f"Failed to trigger ECS task: {str(e)}")
        return False

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for S3 events."""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse S3 event
        for record in event.get('Records', []):
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            # Decode key if URL encoded
            import urllib.parse
            key = urllib.parse.unquote_plus(key)
            
            # Validate file
            is_valid, org_id_or_error, metadata = validate_file(bucket, key)
            
            if not is_valid:
                logger.warning(f"Validation failed for {key}: {org_id_or_error}")
                # Write failed validation audit
                write_audit_record(
                    organization_id='unknown',
                    file_key=key,
                    status='FAILED',
                    step='VALIDATION',
                    details={'error': org_id_or_error, 'bucket': bucket}
                )
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': org_id_or_error})
                }
            
            organization_id = org_id_or_error
            logger.info(f"File validated for organization: {organization_id}")
            
            # Write upload audit record
            write_audit_record(
                organization_id=organization_id,
                file_key=key,
                status='SUCCESS',
                step='UPLOAD',
                details={'bucket': bucket, **metadata}
            )
            
            # Trigger processing
            success = trigger_ecs_task(bucket, key, organization_id, metadata)
            
            if success:
                write_audit_record(
                    organization_id=organization_id,
                    file_key=key,
                    status='SUCCESS',
                    step='TRIGGER',
                    details={'trigger': 'ECS_FARGATE', 'timestamp': datetime.utcnow().isoformat()}
                )
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Processing triggered', 'organization_id': organization_id})
                }
            else:
                write_audit_record(
                    organization_id=organization_id,
                    file_key=key,
                    status='FAILED',
                    step='TRIGGER',
                    details={'error': 'ECS task submission failed'}
                )
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Failed to trigger processing'})
                }
                
    except Exception as e:
        logger.error(f"Unhandled Lambda error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Internal error: {str(e)}"})
        }