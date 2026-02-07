# Lambda Function For QIF Processing & DynamoDB Integration

#### 1. AWS Setup:
    Ensure you have AWS credentials configured

#### 2. Make sure your S3 bucket exists and your Lambda has permission to:
    Read from S3

    Write to DynamoDB

#### 3. Upload & Processing:
    Drop QIF file in S3 bucket

#### 4. Lambda is triggered:
    Reads file from S3

    Parses it into a DataFrame using process_file()

    Saves transactions to DynamoDB via save_transactions_to_db()

#### 5. Local Testing:
    Pytest: python -m pytest

    Run Lambda locally: sam build
                        sam local invoke -e events/event.json
                        (Requires test file in S3: financial-files-bucket/lambda-event-test-example.qif)

#### 6. Deploy Lambda:
    Deploy to aws: sam deploy --resolve-image-repos

#### 7. Usage:
    Upload QIF file to configured S3 bucket

    Lambda is triggered automatically

    Transactions are saved to DynamoDB (FinancialAppDB)