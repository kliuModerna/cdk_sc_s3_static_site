#!/usr/bin/env python3

import aws_cdk as cdk

from cdk_sc_s3_static_site_stack.cdk_sc_s3_static_site_stack import CdkScS3StaticSite


app = cdk.App()
CdkScS3StaticSite(app, "CdkS3StaticSite")

app.synth()
