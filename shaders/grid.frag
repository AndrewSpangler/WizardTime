#version 150

uniform vec2 screen_size; // Size of the screen (width, height)
uniform float grid_spacing; // Spacing between grid lines
uniform vec4 grid_color; // Color of the grid lines
uniform vec4 background_color; // Color of the background

out vec4 fragColor;

void main() {
    vec2 uv = gl_FragCoord.xy / screen_size;
    // normaleize UV to -1.0 to 1.0
    uv = uv * 2.0 - 1.0;
    uv = uv * vec2(screen_size.x / screen_size.y, 1.0) * 40;
    vec2 grid_pos = abs(fract(uv / grid_spacing - 0.5) - 0.5);
    float line_width = 0.01;
    float grid_line = step(grid_pos.x, line_width) + step(grid_pos.y, line_width);
    fragColor = mix(background_color, grid_color, grid_line);
}
