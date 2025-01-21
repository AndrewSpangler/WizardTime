#version 150
uniform vec2 positions[255];
uniform vec4 colors[255];
uniform float radii[255];

uniform int circle_count;
uniform vec2 screen_size;
uniform sampler2D p3d_Texture0;  // Texture sampler

out vec4 fragColor;

void processBuffer(vec2 pos[255], vec4 cols[255], float rad[255], inout vec4 fragColor, vec2 uv, int count) {
    for (int i = 0; i < count; i++) {
        vec2 circle_pos = vec2(pos[i][0], pos[i][1]) / vec2(20);
        float dist = length(uv - circle_pos);

        if (dist < ((rad[i] / 40.0)*0.75)) {
            fragColor = cols[i]; // Circle Fill
        } else if (dist < ((rad[i] * 0.9) / 40.0)) { // Outline Thickness
            fragColor = vec4(cols[i].rgb * 0.5, cols[i].a); // Outline
        } else if (dist < ((rad[i] * 1) / 40.0)) {
            fragColor = cols[i].rgba * cos(dist*80-rad[i]) + vec4(0,0,0,0) * sin(dist*80-rad[i]);
        }
    }
}

void main() {
    vec2 uv = gl_FragCoord.xy / screen_size;
    uv = uv * 2.0 - 1.0; // Normalize UV to -1 to 1
    uv = uv * vec2(screen_size[0] / screen_size[1], 1);
    fragColor = vec4(0, 0, 0, 0);
    processBuffer(positions, colors, radii, fragColor, uv, circle_count);
}