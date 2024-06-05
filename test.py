# Using python:
# 1) Create a python virtual env and activate the env.
# 	cmd: python -m venv boto3_task
# 	cmd: source ./boto3_task/Source/activate
# 2) Install the boto3 library.
# 	Cmd: pip install boto3
# 3) Before using boto3 (aws sdk) create an IAM User and attach necessary policies.

# Make sure you do atleast one of this for making sure python has access to the AWS and make API calls:
# i) configure your AWS CLI
# ii) create config file in location ~/.aws and save them over there.
# iii) simply add them as a environment variables.
# iv) create a shared credentials folder and access it from there

# I followed method 1.

# Import AWS boto3 (Amazon's SDK).
import boto3

# Initialise clients:
ec2_client = boto3.client('ec2')
ec2_resource = boto3.resource('ec2')

# Defining CIDR range:
vpc_cidr_block = '10.0.0.0/18'
vpc_tag = 'harsha_vpc_demo_1'

# Create VPC
vpc = ec2_client.create_vpc(CidrBlock = vpc_cidr_block,
                            TagSpecifications=[
                                                    {
                                                        'ResourceType':'vpc' ,
                                                        'Tags': [
                                                            {
                                                                'Key': 'Name',
                                                                'Value': vpc_tag
                                                            },
                                                        ]
                                                    },
                                                ]
                            )

# Fetch VPC ID
vpc_id = vpc['Vpc']['VpcId']

# Connect an internet gateway to the VPC:
igw_tag = 'harsha_demo_igw'
igw = ec2_client.create_internet_gateway(
    TagSpecifications=[
                        {
                            'ResourceType': 'internet-gateway',
                            'Tags': [
                                {
                                    'Key': 'string',
                                    'Value': igw_tag
                                },
                            ]
                        },
                        ]
    )

# Fetch igw id
igw_id = igw['InternetGateway']['InternetGatewayId']

# Attach the IGW to VPC:
ec2_client.attach_internet_gateway(InternetGatewayId=igw_id,
    VpcId=vpc_id)

# Generic route table code:
def createRouteTables(vpc_id,rt_tag):
    route_table = ec2_client.create_route_table(VpcId = vpc_id,
                                                TagSpecifications=[
        {
            'ResourceType':'route-table',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': rt_tag
                },
            ]
        },
    ]
                                                )
    return route_table


# Creating 2 private route tables and 1 public route tables:

routeTableTags = ["Public_rt_1","Private_rt_1","Private_rt_2"]
routeTables = []
routeTable_ids = dict()
for rt_tag in routeTableTags:
    routeTables.append(createRouteTables(rt_tag=rt_tag,vpc_id=vpc_id))
    routeTable_ids[rt_tag] = routeTables[-1]['RouteTable']['RouteTableId']
print(routeTables)

# Creating public subnet in availability zones us-east-1a and 1b

pub_subnet_cidr = ['10.0.0.0/24','10.0.2.0/24'] # '10.0.0.0/24' ---> Min: 10.0.0.1 to Max: 10.0.0.254
                                                # '10.0.2.0/24' ---> Min: 10.0.2.1 to Max: 10.0.2.254
pub_subnet_tags = ['Harsha_Pub_sub_1','Harsha_Pub_sub_2']
pub_subnet_ids = []
for i,subnet_cidr in enumerate(pub_subnet_cidr):
    subnet = ec2_client.create_subnet(
         TagSpecifications=[
        {
            'ResourceType': 'subnet',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': pub_subnet_tags[i]
                },
            ]
        },
    ],
    CidrBlock= subnet_cidr,
    VpcId=vpc_id
    )
    # Fetch subnet ID
    subnet_id = subnet['Subnet']['SubnetId']
    pub_subnet_ids.append(subnet_id)

    # Associate each public subnet to the public route table:
    ec2_client.associate_route_table(
    RouteTableId=routeTable_ids['Public_rt_1'],
    SubnetId=subnet_id)


# Creating private subnets in the same availability zone as public subnets:

private_subnet_cidr = ['10.0.63.0/25','10.0.32.0/25']
private_subnet_ids = []
private_subnet_tags = ['Harsha_Private_Subnet_1','Harsha_Private_Subnet_2']

for i,subnet_cidr in enumerate(private_subnet_cidr):
    subnet = ec2_client.create_subnet(
        TagSpecifications=[
        {
            'ResourceType': 'subnet',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': private_subnet_tags[i]
                },
            ]
        },
    ],
    CidrBlock= subnet_cidr,
    VpcId=vpc_id
    )

    # Fetch the private subnet ids
    private_subnet_id = subnet['Subnet']['SubnetId']
    private_subnet_ids.append(private_subnet_id)


    # Associate the private subnets with the private route table
    ec2_client.associate_route_table(
        RouteTableId=routeTable_ids['Private_rt_'+str(i+1)],
        SubnetId=subnet['Subnet']['SubnetId']
    )


# Allocate an elastic ip for NAT Gateway in VPC:

EIP_tag = 'Harsha_EIP'
EIP = ec2_client.allocate_address(
    Domain='vpc',
    TagSpecifications=[
        {
            'ResourceType': 'elastic-ip',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': EIP_tag
                },
            ]
        },
    ]
)

AllocationId = EIP['AllocationId']

# Create NAT Gateway in one of the public subnets:
NAT_tag = 'Harsha_NAT_GW'
NAT_Gateway = ec2_client.create_nat_gateway(
    AllocationId=AllocationId,
    SubnetId=pub_subnet_ids[0],
    TagSpecifications=[
        {
            'ResourceType': 'natgateway',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': NAT_tag
                },
            ]
        },
    ]
)

# Checks the status for every 10 until NAT GW becomes available.
import time
NAT_Gateway_id = NAT_Gateway['NatGateway']['NatGatewayId']
while True:
    nat_gate_status = ec2_client.describe_nat_gateways(
        NatGatewayIds = [NAT_Gateway_id]
    )['NatGateways'][0]['State']

    if nat_gate_status == 'available':
        break
    time.sleep(10)

# Create EC2 instances in 2 private subnets:

private_ec2_ids = []
for i, subnet_id in enumerate(private_subnet_ids):
    private_ec2 = ec2_resource.create_instances(ImageId="ami-0d7a109bf30624c99",
                                            MinCount = 1,
                                            MaxCount = 1,
                                            InstanceType = 't2.micro',
                                            NetworkInterfaces=[
                                                {
                                                    'SubnetId':private_subnet_ids[0],
                                                    'DeviceIndex':0,
                                                    'AssociatePublicIpAddress': False
                                                }
                                            ]
                                            )

    private_ec2_id = private_ec2[0].id
    private_ec2_ids.append(private_ec2_id)

# Creating S3 enpoint
endpoint_s3_response = ec2_client.create_vpc_endpoint(
    VpcId=vpc_id,
    ServiceName='com.amazonaws.us-east-1.s3',
    RouteTableIds=[routeTable_ids['Private_rt_1']]
)

# Create VPC endpoint for DynamoDB
endpoint_dynamodb_response = ec2_client.create_vpc_endpoint(
    VpcId=vpc_id,
    ServiceName='com.amazonaws.us-east-1.dynamodb',
    RouteTableIds=[routeTable_ids['Private_rt_2']]
)

# Create a route from public route table to IGW:
ec2_client.create_route(
    DestinationCidrBlock='0.0.0.0/0',
    GatewayId=igw_id,
    RouteTableId=routeTable_ids['Public_rt_1'],
)

# Creates routes for both private route tables to direct traffic to the NAT Gateway
for i in range(2):
    ec2_client.create_route(
        DestinationCidrBlock='0.0.0.0/0',
        NatGatewayId=NAT_Gateway_id,
        RouteTableId=routeTable_ids['Private_rt_'+str(i+1)]
)
    
# We can further extend it to delete the resources created as well using the methods like
    # 1) delete_vpc()
    # 1) delete_internet_gateway() etc...
