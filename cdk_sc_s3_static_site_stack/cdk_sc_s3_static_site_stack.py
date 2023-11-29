from constructs import Construct
from aws_cdk import (
    Aws,
    Stack,
    Tags,
    aws_s3 as s3,
    aws_servicecatalog as sc,
    aws_cloudfront as cloudfront,
    aws_kms as kms,
    aws_iam as iam,
    aws_ssm as ssm,
    RemovalPolicy,
    CfnOutput,
    CfnParameter
)


class S3StaticSiteProduct(sc.ProductStack):
    def __init__(self, scope, id):
        super().__init__(scope, id)

        # S3 bucket name is a user input parameter, bucket name checker applied
        bucket_name_param = CfnParameter(
            self,
            "bucketNameParameter",
            type="String",
            allowed_pattern="(?!(^xn--|.+-s3alias$))^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]",
            description="Define static website bucket name. "
                        "Note: bucket name is not used for the static website domain name",
        )

        sponsor = CfnParameter(
            self,
            "Sponsor",
            type="String",
            allowed_pattern="[a-zA-Z]+(\.[a-zA-Z]+)?@modernatx\.com",
            description="Sponsor email",
        )

        # Create a KMS key
        my_key = kms.Key(
            self,
            "MyUniqueKey",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create a private S3 bucket
        my_bucket = s3.Bucket(
            self,
            "MyUniqueBucketProduct",
            bucket_name=bucket_name_param.value_as_string,
            versioned=True,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=my_key,
            public_read_access=False,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create an Origin Access Control for CloudFront
        oac = cloudfront.CfnOriginAccessControl(
            self,
            "MyCfnOriginAccessControlId",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name=f"{my_bucket.bucket_name} OAC",
                origin_access_control_origin_type="s3",
                signing_behavior="always",
                signing_protocol="sigv4",
                description="Use origin access control (OAC) with an Amazon S3 origin"
            )
        )

        # Create a cloudfront distribution with a private bucket as the origin
        distribution_config_property = cloudfront.CfnDistribution.DistributionConfigProperty(
            origins=[cloudfront.CfnDistribution.OriginProperty(
                domain_name=my_bucket.bucket_regional_domain_name,
                id="myS3OriginId",
                origin_access_control_id=oac.ref,
                s3_origin_config=cloudfront.CfnDistribution.S3OriginConfigProperty()
            )],
            default_cache_behavior=cloudfront.CfnDistribution.DefaultCacheBehaviorProperty(
                target_origin_id="myS3OriginId",
                viewer_protocol_policy="redirect-to-https",
                allowed_methods=["GET", "HEAD"],
                cached_methods=["GET", "HEAD"],
                # id for CachingOptimized cache policy
                cache_policy_id="658327ea-f89d-4fab-a63d-7e88639e58f6",
                compress=False,
            ),
            enabled=True,
            ipv6_enabled=True,
            default_root_object="index.html",

            price_class="PriceClass_All",
            restrictions=cloudfront.CfnDistribution.RestrictionsProperty(
                geo_restriction=cloudfront.CfnDistribution.GeoRestrictionProperty(
                    restriction_type="whitelist",
                    locations=["US", "JP", "CA", "IN"]
                )
            ),
            viewer_certificate=cloudfront.CfnDistribution.ViewerCertificateProperty(
                cloud_front_default_certificate=True,
            ),
        )

        my_distribution = cloudfront.CfnDistribution(
            self,
            "MyCloudFrontDistribution",
            distribution_config=distribution_config_property
        )

        # Add a bucket policy that allows CloudFront read-access the bucket
        my_bucket.add_to_resource_policy(iam.PolicyStatement(
            sid="AllowCloudFrontServicePrincipalReadOnly",
            actions=["s3:GetObject"],
            principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
            resources=[
                my_bucket.bucket_arn,
                my_bucket.arn_for_objects('*')
            ],
            conditions={
                "StringEquals": {
                    f"aws:SourceArn": f"arn:aws:cloudfront::{Aws.ACCOUNT_ID}:distribution/{my_distribution.ref}"
                }
            }
        ))

        # KMS key policy statement that allows a CloudFront OAC to access a KMS key for SSE-KMS
        my_key.add_to_resource_policy(iam.PolicyStatement(
            sid="AllowCloudFrontServicePrincipalSSE-KMS",
            actions=[
                "kms:Decrypt",
                "kms:Encrypt",
                "kms:GenerateDataKey*"
            ],
            principals=[
                iam.ServicePrincipal("cloudfront.amazonaws.com")
            ],
            resources=["*"]
        ))

        Tags.of(my_bucket).add("Sponsor", sponsor.value_as_string)
        Tags.of(my_key).add("Sponsor", sponsor.value_as_string)
        Tags.of(my_distribution).add("Sponsor", sponsor.value_as_string)

        # Output the CloudFront URL
        CfnOutput(
            self,
            "DistributionDomainName",
            value=f"https://{my_distribution.attr_domain_name}",
            description="The domain name of the CloudFront distribution"
        )


class CdkScS3StaticSite(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        tag_options = sc.TagOptions(
            self,
            'TagOptions',
            allowed_values_for_tags=scope.node.try_get_context("tag_options"))

        infra_portfolio = sc.Portfolio(
            self,
            'InfrastructurePortfolio',
            display_name='Infrastructure Portfolio',
            description='Potfolio with approved list of infrastructure products',
            provider_name='Cloud Infra Team',
            tag_options=tag_options
        )

        product_from_stack = sc.CloudFormationProduct(
            self,
            "SCProduct_S3_Static_Site",
            product_name='S3_CloudFront',
            owner="kliu",
            description='Host static sites in aws using S3, cloudfront. It creates a private S3 bucket and uses '
                        'S3 endpoint as an origin in cloudfront and Origin Access Control (OAC) '
                        'to access the S3 objects.',
            product_versions=[
                sc.CloudFormationProductVersion(
                    product_version_name="v1.0",
                    cloud_formation_template=sc.CloudFormationTemplate.from_product_stack(
                        S3StaticSiteProduct(
                            self,
                            "S3StaticSiteProduct"
                        )
                )
            )]
        )


        product_from_stack.associate_tag_options(tag_options)

        # Associate product to the portfolio
        infra_portfolio.add_product(product_from_stack)
