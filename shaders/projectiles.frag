#version 430

struct Projectile {
    // First 4 floats
    vec2 position;
    float scale;
    float spawn;
    // Second 4 floats
    vec4 color;
};

layout(std430, binding = 0) buffer projectileData {
    Projectile projectiles[255];
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
        Projectile proj = projectiles[_i];
        vec2 tex_center = proj.position / 20.0;
        vec2 tex_uv = (uv - tex_center) / (proj.scale / 20.0) + 0.5;

        // Skip outside texture bounds
        if (tex_uv.x < 0.0 || tex_uv.x > 1.0 || tex_uv.y < 0.0 || tex_uv.y > 1.0) {
            continue;
        }

        vec4 tex_color = texture(p3d_Texture0, tex_uv);
        fragColor = mix(fragColor, tex_color * proj.color, tex_color.a);

        // Exit if fully opaque since lower layers won't contribute
        if (fragColor.a >= 1.0) {
            break;
        }
    }
}
