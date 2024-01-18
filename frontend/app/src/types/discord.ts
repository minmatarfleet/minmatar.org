export interface DiscordUser {
    id:                 string;
    username:           string;
    discriminator:      string;
    global_name?:       string;
    avatar?:            string;
    bot?:               boolean;
    system?:            boolean;
    mfa_enabled?:       boolean;
    banner?:            string;
    accent_color?:      integer;
    locale?:            string;
    verified?:          boolean;
    email?:             string;
    flags?:             integer;
    premium_type?:      integer;
    public_flags?:      integer;
    avatar_decoration?: string;
}