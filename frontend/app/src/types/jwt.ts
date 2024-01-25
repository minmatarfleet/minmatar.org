export type JWTCookies = JWT | boolean

export interface JWT {
    user_id:      number;
    username:     string;
    avatar:       string;
    is_staff:     boolean;
    is_superuser: boolean;
    permissions:  string[];
}