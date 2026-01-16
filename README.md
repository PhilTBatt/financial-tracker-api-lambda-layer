# Lambda Function For QIF Processing & DynamoDB Integration

#### 1. AWS Setup:
    Ensure you have AWS credentials configured

#### 2. Make sure your S3 bucket exists and your Lambda has permission to:
    Read from S3

    Write to DynamoDB (FinancialAppDB)

#### 3. Upload & Processing:
    Drop QIF file in S3 bucket (configured for your Lambda).

#### 4. Lambda is triggered:
    Reads file from S3

    Parses it into a DataFrame using process_file()

    Saves transactions to DynamoDB via save_transactions_to_db()

#### 5. Testing process_file():
    Run pytest test: pytest -s

#### 6. Build & Deploy Lambda:
    Build the labda: sam build

    Deploy to aws: sam deploy --guided

#### 7. Usage:
    Upload QIF file to configured S3 bucket

    Lambda is triggered automatically

    Transactions are saved to DynamoDB (FinancialAppDB)