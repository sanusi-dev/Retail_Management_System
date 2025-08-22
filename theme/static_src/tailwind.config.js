// theme/static_src/tailwind.config.js
module.exports = {
    // This makes sure Tailwind scans your files for classes
    content: [
        "../../../**/templates/**/*.{html,js,py}",
        "../../../**/static/js/**/*.js",
        "../../../**/forms.py",
        // Add Flowbite's JS content path here if you're using their components
        // for example: "./node_modules/flowbite/**/*.js"
    ],

    darkMode: 'class', // Correctly placed at the top level of the config object

    theme: {
        extend: {
            colors: {
                primary: { "50": "#eff6ff", "100": "#dbeafe", "200": "#bfdbfe", "300": "#93c5fd", "400": "#60a5fa", "500": "#3b82f6", "600": "#2563eb", "700": "#1d4ed8", "800": "#1e40af", "900": "#1e3a8a", "950": "#172554" }
            },
            fontFamily: {
                'body': [
                    'Inter',
                    'ui-sans-serif',
                    'system-ui',
                    '-apple-system',
                    'system-ui',
                    'Segoe UI',
                    'Roboto',
                    'Helvetica Neue',
                    'Arial',
                    'Noto Sans',
                    'sans-serif',
                    'Apple Color Emoji',
                    'Segoe UI Emoji',
                    'Segoe UI Symbol',
                    'Noto Color Emoji'
                ],
                'sans': [
                    'Inter',
                    'ui-sans-serif',
                    'system-ui',
                    '-apple-system',
                    'system-ui',
                    'Segoe UI',
                    'Roboto',
                    'Helvetica Neue',
                    'Arial',
                    'Noto Sans',
                    'sans-serif',
                    'Apple Color Emoji',
                    'Segoe UI Emoji',
                    'Segoe UI Symbol',
                    'Noto Color Emoji'
                ]
            }
        },
    },

    plugins: [
        require('daisyui'),
        require('flowbite/plugin') // Add Flowbite's plugin
    ],

    // This is the most important part!
    // We are configuring DaisyUI to NOT add its own base styles.
    daisyui: {
        styled: true,
        themes: true,
        base: true, // <--- THIS IS THE FIX. Disables DaisyUI's base style reset.
        utils: true,
        logs: true,
        rtl: false,
        prefix: "",
        darkTheme: "dark",
    },
};