# src/processor/processor.py - Main Processing Logic

import os
import json
import logging
import boto3
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables (set by Lambda via overrides)
FILE_BUCKET = os.environ.get('FILE_BUCKET')
FILE_KEY = os.environ.get('FILE_KEY')
ORGANIZATION_ID = os.environ.get('ORGANIZATION_ID')
FILE_SIZE = os.environ.get('FILE_SIZE', '0')
FILE_ETAG = os.environ.get('FILE_ETAG', '')

# Fixed environment variables from task definition
AUDIT_TABLE_NAME = os.environ.get('AUDIT_TABLE_NAME')
INGRESS_BUCKET = os.environ.get('INGRESS_BUCKET')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
KMS_KEY_ID = os.environ.get('KMS_KEY_ID')

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(AUDIT_TABLE_NAME)

def write_audit_record(step: str, status: str, details: Dict[str, Any]) -> None:
    """Write audit record with standardized format."""
    timestamp = datetime.utcnow().isoformat()
    
    record = {
        'PK': f"FILE#{FILE_KEY}",
        'SK': f"{timestamp}#{step}",
        'OrganizationId': ORGANIZATION_ID,
        'FileKey': FILE_KEY,
        'Status': status,
        'Step': step,
        'EventTimestamp': timestamp,
        'Details': json.dumps(details)
    }
    
    try:
        table.put_item(Item=record)
        logger.info(f"Audit written: {step} -> {status}")
    except Exception as e:
        logger.error(f"Failed to write audit: {str(e)}")
        raise

def download_and_process() -> bool:
    """Simulate processing: download file, log metadata, then clean up."""
    try:
        # Write processing start audit
        write_audit_record('PROCESSING_START', 'RUNNING', {
            'file_bucket': FILE_BUCKET,
            'file_key': FILE_KEY,
            'file_size': FILE_SIZE,
            'file_etag': FILE_ETAG
        })
        
        # Download file (in real scenario, we'd process the data)
        logger.info(f"Downloading {FILE_KEY} from {FILE_BUCKET}")
        response = s3_client.get_object(Bucket=FILE_BUCKET, Key=FILE_KEY)
        
        # Simulate processing: read a bit of the file
        file_content = response['Body'].read(1024)  # Read first 1KB for logging
        file_preview = file_content[:100].hex() if file_content else "empty"
        
        # Log processing details
        logger.info(f"Processing file: {FILE_KEY}")
        logger.info(f"Organization: {ORGANIZATION_ID}")
        logger.info(f"File size: {FILE_SIZE} bytes")
        logger.info(f"Content type: {response.get('ContentType', 'unknown')}")
        logger.info(f"First 100 bytes (hex): {file_preview}")
        
        # Simulate some work (in real scenario, this would be meaningful)
        import time
        time.sleep(2)  # Simulate processing delay
        
        # Write completion audit
        write_audit_record('PROCESSING_COMPLETE', 'SUCCESS', {
            'processed_bytes': response['ContentLength'],
            'processing_duration_seconds': 2,
            'file_key': FILE_KEY
        })
        
        return True
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}", exc_info=True)
        write_audit_record('PROCESSING_COMPLETE', 'FAILED', {
            'error': str(e),
            'error_type': type(e).__name__
        })
        return False

def main():
    """Main entry point for processor."""
    logger.info(f"Starting processor for file: {FILE_KEY}, org: {ORGANIZATION_ID}")
    
    # Validate required environment variables
    if not all([FILE_BUCKET, FILE_KEY, ORGANIZATION_ID, AUDIT_TABLE_NAME]):
        logger.error("Missing required environment variables")
        write_audit_record('PROCESSING_START', 'FAILED', {
            'error': 'Missing required environment variables',
            'missing': {
                'FILE_BUCKET': bool(FILE_BUCKET),
                'FILE_KEY': bool(FILE_KEY),
                'ORGANIZATION_ID': bool(ORGANIZATION_ID),
                'AUDIT_TABLE_NAME': bool(AUDIT_TABLE_NAME)
            }
        })
        sys.exit(1)
    
    success = download_and_process()
    
    if success:
        logger.info("Processing completed successfully")
        sys.exit(0)
    else:
        logger.error("Processing failed")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    main()