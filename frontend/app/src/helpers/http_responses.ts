export const HTTP_404_Not_Found = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 404,
        statusText: 'Not found'
    });
}

export const HTTP_403_Forbidden = () => {
    return new Response(
        `<!doctype html>
            <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <title>403 Unauthorized</title>
                    <meta name="description" content="Docking request denied!">
                    <link rel="icon" type="image/svg+xml" href="/images/fleet-logo.png">

                    <style>
                        body {
                            background-color: #121212;
                        }
                    </style>
                    
                    <script>
                        async function fetchAndReplace(url) {
                            try {
                                // Fetch the new page content
                                const response = await fetch(url);
                    
                                if (!response.ok) {
                                    throw new Error(\`Error fetching the page: \${response.status} \${response.statusText}\`);
                                }
                    
                                // Get the response as text
                                const newHTML = await response.text();
                    
                                // Replace the entire page's HTML
                                document.open(); // Clear the current document
                                document.write(newHTML); // Write the new content
                                document.close(); // Close the document to finalize changes
                            } catch (error) {
                                console.error("Error replacing page content:", error);
                            }
                        }
                    
                        fetchAndReplace("/403");
                    </script>
                </head>
                <body></body>
            </html>`, {
            status: 403,
            headers: { 'Content-type': 'text/html' },
            statusText: 'Forbidden',
        }
    ) as Response;
}

export const HTTP_200_Success = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 200,
        statusText: 'Success'
    });
}

export const HTTP_400_Bad_Request = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 400,
        statusText: 'Bad Request'
    });
}

export const HTTP_500_Server_Error = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 500,
        statusText: 'Server Error'
    });
}

export const HTTP_502_Server_Error = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 502,
        statusText: 'Service Unavailable'
    });
}