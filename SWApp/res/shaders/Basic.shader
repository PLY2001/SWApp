#shader vertex
#version 330 core 

layout(location=0) in vec3 position; 
layout(location=1) in vec3 normal;
layout(location=2) in vec2 texcoord; //贴图坐标
layout(location=3) in mat4 model; 

out VS_OUT{
	vec2 v_texcoord;//传递（vary）给片元着色器的变量
	vec4 v_WorldNormal;
	//vec4 v_ViewNormal;
	vec4 v_WorldPosition;
}vs_out;


layout(std140) uniform Matrices
{
	mat4 u_view;
	mat4 u_projection;
};


void main() 
{ 
	vs_out.v_texcoord=texcoord;
	vs_out.v_WorldNormal=model*vec4(normalize(normal),0.0f);
	//vs_out.v_ViewNormal=u_view*model*vec4(normalize(normal),0.0f);
	vs_out.v_WorldPosition=model*vec4(position,1.0f);
	gl_Position =u_projection*u_view*model*vec4(position,1.0f); 

}






#shader fragment
#version 330 core 

struct Material
{
	sampler2D texture_diffuse1;
	sampler2D texture_specular1;
	//sampler2D texture_normal1;
};

out vec4 color; 

uniform Material material;
uniform vec3 MBDColor;
uniform int viewType;
uniform sampler2D depth_R_map;
uniform float WinWidth;
uniform float WinHeight;


in VS_OUT{
	vec2 v_texcoord;//从顶点着色器传入的变量
	vec4 v_WorldNormal;
	vec4 v_WorldPosition;
}fs_in;


void main() 
{
    vec3 worldLight1 = normalize(vec3(1.0f,1.4f,1.2f)); //获取光源位置
    vec3 worldLight2 = normalize(vec3(-1.0f,-1.5f,-1.3f)); //获取光源位置
	vec3 lightColor = vec3(1.0f);
	vec3 diffuseColor = vec3(0.9f);
    vec3 diffuse = lightColor * diffuseColor * (max(0, dot(worldLight1, normalize(fs_in.v_WorldNormal.xyz))) + max(0, dot(worldLight2, normalize(fs_in.v_WorldNormal.xyz)))); // 计算漫反射
    //vec3 diffuse = fs_in.v_WorldNormal.xyz*0.5 +vec3(0.5); // 法线
	float depth = float(gl_FragCoord.z);
	vec2 uv = vec2(gl_FragCoord.x/WinWidth, gl_FragCoord.y/WinHeight);
	float depth_R = texture(depth_R_map,uv).r;
	float houdu = 1.0f - (depth_R - depth);
	vec3 finalColor = viewType > -1 ? MBDColor : vec3(1.0,0.0,0.0);
	if(viewType == 1){
		finalColor.x = houdu;
	}
	finalColor = viewType > 1 ? diffuse : finalColor;
	finalColor = viewType > 2 ? vec3(houdu) : finalColor;
	color =vec4(finalColor,1.0f);//*(1.0f-shadowColor) //texColor;//u_color;//vec4(0.2,0.7,0.3,1.0); 
}