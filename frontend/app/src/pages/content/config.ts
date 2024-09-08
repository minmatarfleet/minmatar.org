import { z, defineCollection } from 'astro:content';

const blog_collection = defineCollection({
    type: 'content',
    schema: z.object({
        title: z.string(),
        tags: z.array(z.string()),
        image: z.string().optional(),
        author: z.string(),
        author_id: z.number(),
        description: z.string(),
    }),
});

export const collections = {
    'blog': blog_collection,
};