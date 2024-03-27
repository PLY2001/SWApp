#include "Texture.h"


Texture::Texture(const std::string& path):RendererID(0),FilePath(path),LocalBuffer(nullptr),Width(0),Height(0),BBP(0)
{
	stbi_set_flip_vertically_on_load(1);//垂直翻转纹理，因为OpenGL图片原点在左下角，而png图片读取是从左上角开始。
	LocalBuffer = stbi_load(path.c_str(), &Width, &Height, &BBP, 4);//使用stb_image库函数加载图片。

	glGenTextures(1, &RendererID);
	glBindTexture(GL_TEXTURE_2D, RendererID);

	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);//设置纹理过滤方式（必须设置）
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);//设置纹理过滤方式（必须设置）
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);//设置纹理环绕方式（必须设置）
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);//设置纹理环绕方式（必须设置）

	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, Width, Height, 0, GL_RGBA, GL_UNSIGNED_BYTE, LocalBuffer);//将读取的图片存入贴图
	glBindTexture(GL_TEXTURE_2D, 0);

	if (LocalBuffer)//存入贴图成功后，可以清除读取的图片缓存
		stbi_image_free(LocalBuffer);
}
Texture::~Texture()
{
	glDeleteTextures(1, &RendererID);
}

void Texture::Bind(unsigned int slot) const
{
	glActiveTexture(GL_TEXTURE0+slot);//绑定纹理前，要先激活对应的纹理单元，索引为“0+slot”（索引为0的单元OpenGL是会自动激活的）
	glBindTexture(GL_TEXTURE_2D, RendererID);
}
void Texture::Unbind() const
{
	glBindTexture(GL_TEXTURE_2D, 0);
}

