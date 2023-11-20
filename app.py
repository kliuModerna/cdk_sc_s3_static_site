#!/usr/bin/env python3

import aws_cdk as cdk

from cdk_sc_level2_workshop.cdk_sc_level2_workshop_stack import CdkScLevel2WorkshopStack


app = cdk.App()
CdkScLevel2WorkshopStack(app, "CdkScLevel2WorkshopStack")

app.synth()
