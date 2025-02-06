/// <reference types="astro/client" />

declare module "astro" {
    interface Locals {
        clientIP: string;
    }
}