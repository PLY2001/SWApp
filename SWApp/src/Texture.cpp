#include "Texture.h"


Texture::Texture(const std::string& path):RendererID(0),FilePath(path),LocalBuffer(nullptr),Width(0),Height(0),BBP(0)
{
	stbi_set_flip_vertically_on_load(1);//��ֱ��ת������ΪOpenGLͼƬԭ�������½ǣ���pngͼƬ��ȡ�Ǵ����Ͻǿ�ʼ��
	LocalBuffer = stbi_load(path.c_str(), &Width, &Height, &BBP, 4);//ʹ��stb_image�⺯������ͼƬ��

	glGenTextures(1, &RendererID);
	glBindTexture(GL_TEXTURE_2D, RendererID);

	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);//����������˷�ʽ���������ã�
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);//����������˷�ʽ���������ã�
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);//���������Ʒ�ʽ���������ã�
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);//���������Ʒ�ʽ���������ã�

	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, Width, Height, 0, GL_RGBA, GL_UNSIGNED_BYTE, LocalBuffer);//����ȡ��ͼƬ������ͼ
	glBindTexture(GL_TEXTURE_2D, 0);

	if (LocalBuffer)//������ͼ�ɹ��󣬿��������ȡ��ͼƬ����
		stbi_image_free(LocalBuffer);
}
Texture::~Texture()
{
	glDeleteTextures(1, &RendererID);
}

void Texture::Bind(unsigned int slot) const
{
	glActiveTexture(GL_TEXTURE0+slot);//������ǰ��Ҫ�ȼ����Ӧ������Ԫ������Ϊ��0+slot��������Ϊ0�ĵ�ԪOpenGL�ǻ��Զ�����ģ�
	glBindTexture(GL_TEXTURE_2D, RendererID);
}
void Texture::Unbind() const
{
	glBindTexture(GL_TEXTURE_2D, 0);
}

