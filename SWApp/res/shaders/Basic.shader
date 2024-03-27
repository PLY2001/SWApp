#shader vertex
#version 330 core 

layout(location=0) in vec3 position; 
layout(location=1) in vec3 normal;
layout(location=2) in vec2 texcoord; //��ͼ����
layout(location=3) in mat4 model; 

out VS_OUT{
	vec2 v_texcoord;//���ݣ�vary����ƬԪ��ɫ���ı���
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
uniform float type;
uniform float isDatum;

in VS_OUT{
	vec2 v_texcoord;//�Ӷ�����ɫ������ı���
	vec4 v_WorldNormal;
	vec4 v_WorldPosition;
}fs_in;


void main() 
{

	float depth = float(gl_FragCoord.z);


	
	color =vec4(depth,isDatum*0.7f,type,1.0f);//*(1.0f-shadowColor) //texColor;//u_color;//vec4(0.2,0.7,0.3,1.0); 
}