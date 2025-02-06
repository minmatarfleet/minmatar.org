/// <reference path="../../.astro/types.d.ts" />
/// <reference types="astro/client" />

declare module "astro" {
    interface Locals {
        clientIP: string;
    }
}