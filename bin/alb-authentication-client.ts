#!/usr/bin/env node
import 'source-map-support/register';
import { App } from 'aws-cdk-lib';
import { AlbAuthenticationClientStack } from '../lib/alb-authentication-client-stack';

const app = new App();
new AlbAuthenticationClientStack(app, 'AlbAuthenticationClientStack', {
});