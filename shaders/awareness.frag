#version 150
uniform vec2 positions[255];
uniform vec2 radii[255];

uniform int circle_count;
uniform vec2 screen_size;
uniform sampler2D p3d_Texture0;  // Texture sampler

out vec4 fragColor;

void processBuffer(vec2 pos[255], vec2 rad[255], inout vec4 fragColor, vec2 uv, int count) {
    for (int i = 0; i < count; i++) {
        vec2 circle_pos = vec2(pos[i][0], pos[i][1]) / vec2(20);
        float dist = length(uv - circle_pos);

        vec4 circleColor = vec4(1, 0.2, 0.2, 1);

        if ((dist > (rad[i][1] / 40.255)) && (dist < (rad[i][1] / 40.0))) {
            // Edge of the circle
            circleColor.a = 0.6;
            circleColor.g = 0.6;
        } else if (dist < (rad[i][1] / 40.0) && dist > (rad[i][0] / 41)) {
            // Inside the circle
            circleColor.a = 0.25;
        } else if ((dist > (rad[i][0] / 42)) && (dist < (rad[i][0] / 40.0))) {
            // Edge of the circle
            circleColor.a = 0.6;
        } else if (dist < (rad[i][0] / 40.0)) {
            // Inside the circle
            circleColor.a = 0.25;
        } else {
            continue; // Skip processing if not in circle bounds
        }

        // Apply multiplicative blending
        fragColor = fragColor * (1.0 - circleColor.a) + circleColor * circleColor.a;
    }
}

void main() {
    vec2 uv = gl_FragCoord.xy / screen_size;
    uv = uv * 2.0 - 1.0; // Normalize UV to -1 to 1
    uv = uv * vec2(screen_size[0] / screen_size[1], 1);
    fragColor = vec4(1, 1, 1, 0); // Start with white background
    processBuffer(positions, radii, fragColor, uv, circle_count);

    // Ensure the final color stays in range
    fragColor = clamp(fragColor, 0.0, 1.0);
}
