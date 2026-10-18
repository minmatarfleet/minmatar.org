export interface User {
    user_id:      number;
    username:     string;
    avatar:       string;
    is_superuser: boolean;
    permissions:  string[];
}