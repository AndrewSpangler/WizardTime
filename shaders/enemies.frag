#version 430

struct Drawable {
    // First 4 floats
    vec2 position;
    float scale;
    float type;
    // Second 4 floats
    vec4 color;
    // Third 4 floats
    float max_health;
    float max_shield;
    float health;
    float shield;
};

layout(std430, binding = 0) buffer drawableData {
    Drawable drawables[255];
};

uniform int count;

uniform vec2 screen_size;
uniform sampler2D p3d_Texture0;

out vec4 fragColor;

void main() {
    vec2 uv = (gl_FragCoord.xy / screen_size) * 2.0 - 1.0;
    uv *= vec2(screen_size.x / screen_size.y, 1.0);
    fragColor = vec4(0.0);

    for (int _i = 0; _i < count; _i++) {
        Drawable draw = drawables[_i];
        vec2 tex_center = draw.position / 20.0;
        vec2 tex_uv = (uv - tex_center) / (draw.scale / 20.0) + 0.5;

        // skip if out of bounds
        if (tex_uv.x < 0.0 || tex_uv.x > 1.0 || tex_uv.y < 0.0 || tex_uv.y > 1.0) {
            continue;
        }

        vec4 tex_color = texture(p3d_Texture0, tex_uv);
        fragColor = mix(fragColor, tex_color * draw.color, tex_color.a);

        // bar dimensions
        float bar_width = 0.1;   // Width of the health bar
        float bar_height = 0.02; // Height of the health bar
        vec2 bar_start = draw.position / vec2(20) - vec2(bar_width / 2.0, 0.0);

        // bar proportions
        float health_ratio = draw.health / draw.max_health;
        float shield_ratio = draw.shield / draw.max_shield;

        // base layer
        if (uv.x >= bar_start.x - 0.002 && uv.x <= bar_start.x + bar_width + 0.002 &&
            uv.y >= bar_start.y - 0.002 && uv.y <= bar_start.y + bar_height + 0.002) {
            fragColor = vec4(0.6, 0.6, 0.6, 1.0);
        }

        // health layer
        float health_end_x = bar_start.x + bar_width * health_ratio;
        if (uv.x >= bar_start.x && uv.x <= health_end_x &&
            uv.y >= bar_start.y && uv.y <= bar_start.y + bar_height) {
            fragColor = vec4(1.0, 0.0, 0.0, 1.0);
        }

        // shield layer
        float shield_end_x = bar_start.x + bar_width * shield_ratio;
        if (uv.x >= bar_start.x && uv.x <= shield_end_x &&
            uv.y >= bar_start.y && uv.y <= bar_start.y + bar_height) {
            fragColor = mix(fragColor, vec4(0.0, 0.0, 1.0, 1.0), 0.5);
        }
    
    }
}
