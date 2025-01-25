#version 430

// player, NPCs, etc
struct Drawable {
    // First 4 floats
    vec2 position;
    float scale;
    float type; // Unused
    // Second 4 floats
    vec4 color;
    // Third 4 floats
    float max_health;
    float max_shield;
    float health;
    float shield;
};

layout(std430, binding = 0) buffer EnemyData {
    Drawable enemy_data[255];
};

layout(std430, binding = 0) buffer PlayerData {
    Drawable player_data[1];
};

struct Portal {
    // First 4 floats
    vec2 position;
    float scale;
    float spawn;
    // Second 4 floats
    vec4 color;
};

layout(std430, binding = 0) buffer portalData {
    Portal portals[32];
};

struct Projectile {
    // First 4 floats
    vec2 position;
    float scale;
    float spawn;
    // Second 4 floats
    vec4 color;
};

layout(std430, binding = 0) buffer PlayerProjectileData {
    Projectile player_projectiles[255];
};

layout(std430, binding = 0) buffer EnemyProjectileData {
    Projectile enemy_projectiles[255];
};

uniform int count;
uniform int enemy_count;
uniform int portal_count;
uniform int player_projectile_count;
uniform int enemy_projectile_count;

uniform vec2 screen_size;

uniform sampler2D p3d_Texture0;         //# Texture 0
uniform sampler2D background_texture;   //# Texture 1
uniform sampler2D portal_texture;       //# Texture 2
uniform sampler2D projectile_texture;   //# Texture 3
uniform sampler2D enemy_texture;        //# Texture 3

uniform float grid_spacing;
uniform vec4 grid_color;

out vec4 fragColor;

void draw_projectiles(Projectile projectiles[255], int proj_count, vec2 proj_uv) {
    for (int _i = 0; _i < proj_count; _i++) {
        Projectile proj = projectiles[_i];
        vec2 tex_center = proj.position / 20.0;
        vec2 tex_uv = (proj_uv - tex_center) / (proj.scale / 20.0) + 0.5;

        // Skip outside texture bounds
        if (tex_uv.x < 0.0 || tex_uv.x > 1.0 || tex_uv.y < 0.0 || tex_uv.y > 1.0) {
            continue;
        }

        vec4 tex_color = texture(projectile_texture, tex_uv);
        fragColor = mix(fragColor, tex_color * proj.color, tex_color.a);

        // Exit if fully opaque since lower layers won't contribute
        if (fragColor.a >= 1.0) {
            break;
        }
    }
}


void draw_drawables(Drawable drawables[255], int draw_count, vec2 draw_uv, sampler2D tex) {
    for (int _i = 0; _i < draw_count; _i++) {
        Drawable draw = drawables[_i];
        vec2 tex_center = draw.position / 20.0;
        vec2 tex_uv = (draw_uv - tex_center) / (draw.scale / 20.0) + 0.5;

        // skip if out of bounds
        if (tex_uv.x < 0.0 || tex_uv.x > 1.0 || tex_uv.y < 0.0 || tex_uv.y > 1.0) {
            continue;
        }

        vec4 tex_color = texture(tex, tex_uv);
        fragColor = mix(fragColor, tex_color * draw.color, tex_color.a);

        // bar dimensions
        float bar_width = 0.1;   // Width of the health bar
        float bar_height = 0.02; // Height of the health bar
        vec2 bar_start = draw.position / vec2(20) - vec2(bar_width / 2.0, 0.0);

        // bar proportions
        float health_ratio = draw.health / draw.max_health;
        float shield_ratio = draw.shield / draw.max_shield;

        // base layer
        if (draw_uv.x >= bar_start.x - 0.002 && draw_uv.x <= bar_start.x + bar_width + 0.002 &&
            draw_uv.y >= bar_start.y - 0.002 && draw_uv.y <= bar_start.y + bar_height + 0.002) {
            fragColor = vec4(0.6, 0.6, 0.6, 1.0);
        }

        // health layer
        float health_end_x = bar_start.x + bar_width * health_ratio;
        if (draw_uv.x >= bar_start.x && draw_uv.x <= health_end_x &&
            draw_uv.y >= bar_start.y && draw_uv.y <= bar_start.y + bar_height) {
            fragColor = vec4(1.0, 0.0, 0.0, 1.0);
        }

        // shield layer
        float shield_end_x = bar_start.x + bar_width * shield_ratio;
        if (draw_uv.x >= bar_start.x && draw_uv.x <= shield_end_x &&
            draw_uv.y >= bar_start.y && draw_uv.y <= bar_start.y + bar_height) {
            fragColor = mix(fragColor, vec4(0.0, 0.0, 1.0, 1.0), 0.5);
        }
    }
}

void main() {
    vec2 uv = (gl_FragCoord.xy / screen_size) * 2.0 - 1.0;
    uv *= vec2(screen_size.x / screen_size.y, 1.0);

    // draw background image
    fragColor = vec4(texture(background_texture, uv*4).rgb/2, 1);

    // draw portals
    for (int _i = 0; _i < portal_count*2; _i++) {
        Portal portal = portals[_i];
        vec2 tex_center = portal.position / 20.0;
        vec2 tex_uv = (uv - tex_center) / (portal.scale / 7.0) + 0.5;

        // Skip outside texture bounds
        if (tex_uv.x < 0.0 || tex_uv.x > 1.0 || tex_uv.y < 0.0 || tex_uv.y > 1.0) {
            continue;
        }

        vec4 tex_color = texture(portal_texture, tex_uv);
        fragColor = mix(fragColor, tex_color * portal.color, tex_color.a);

        // Exit if fully opaque since lower layers won't contribute
        if (fragColor.a >= 1.0) {
            break;
        }
    }

    // draw grid

    vec2 grid_pos = abs(fract((uv * 40) / (grid_spacing) - 0.5));
    float line_width = 0.03;
    float grid_line = step(grid_pos.x, line_width) + step(grid_pos.y, line_width);
    fragColor = mix(fragColor, grid_color, grid_line);

    for (int _i = 0; _i < player_projectile_count; _i++) {
        Projectile proj = player_projectiles[_i];
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
    
    // draw enemeies 
    draw_drawables(enemy_data, enemy_count, uv, enemy_texture);
    draw_projectiles(enemy_projectiles, enemy_projectile_count, uv);
    draw_projectiles(player_projectiles, player_projectile_count, uv);

    // draw players and NPCs
    for (int _i = 0; _i < count; _i++) {
        Drawable draw = player_data[_i];
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

        float y_offset = 0.05;

        // base layer
        if (uv.x >= bar_start.x - 0.002 && uv.x <= bar_start.x + bar_width + 0.002 &&
            uv.y >= bar_start.y - 0.002 + y_offset && uv.y <= bar_start.y + bar_height + 0.002 + y_offset) {
            fragColor = vec4(0.6, 0.6, 0.6, 1.0);
        }

        // health layer
        float health_end_x = bar_start.x + bar_width * health_ratio;
        if (uv.x >= bar_start.x && uv.x <= health_end_x &&
            uv.y >= bar_start.y + y_offset && uv.y <= bar_start.y + bar_height + y_offset) {
            fragColor = vec4(1.0, 0.0, 0.0, 1.0);
        }

        // shield layer
        float shield_end_x = bar_start.x + bar_width * shield_ratio;
        if (uv.x >= bar_start.x && uv.x <= shield_end_x &&
            uv.y >= bar_start.y + y_offset && uv.y <= bar_start.y + bar_height + y_offset) {
            fragColor = mix(fragColor, vec4(0.0, 0.0, 1.0, 1.0), 0.5);
        }
    }
}






