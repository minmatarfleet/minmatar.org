export function tag_ids_from_form_data(form_data: FormData): number[] {
    return (form_data.getAll('tag') as string[])
        .map((tag) => parseInt(tag, 10))
        .filter((id) => !Number.isNaN(id))
}
