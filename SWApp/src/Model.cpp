#include "Model.h"


Model::Model(std::string path)
{
	Assimp::Importer import;
	const aiScene* scene = import.ReadFile(path, aiProcess_Triangulate | aiProcess_FlipUVs);// | aiProcess_CalcTangentSpace);

	if (!scene || scene->mFlags & AI_SCENE_FLAGS_INCOMPLETE || !scene->mRootNode)
	{
		std::cout << "ERROR::ASSIMP::" << import.GetErrorString() << std::endl;
		return;
	}
	directory = path.substr(0, path.find_last_of('/'));
	processNode(scene->mRootNode, scene);

	//SetPosition();
}


void Model::processNode(aiNode* node, const aiScene* scene)
{
	// 处理节点所有的网格（如果有的话）
	for (unsigned int i = 0; i < node->mNumMeshes; i++)
	{
		aiMesh* mesh = scene->mMeshes[node->mMeshes[i]];
		meshes.push_back(processMesh(mesh, scene));
	}
	// 接下来对它的子节点重复这一过程
	for (unsigned int i = 0; i < node->mNumChildren; i++)
	{
		processNode(node->mChildren[i], scene);
	}
}

Mesh Model::processMesh(aiMesh* mesh, const aiScene* scene)
{
	std::vector<Vertex> vertices;
	std::vector<unsigned int> indices;
	std::vector<myTexture> textures;
	for (unsigned int i = 0; i < mesh->mNumVertices; i++)
	{
		Vertex vertex;
		vertex.Position.x = mesh->mVertices[i].x;
		vertex.Position.y = mesh->mVertices[i].y;
		vertex.Position.z = mesh->mVertices[i].z;
	
		vertex.Normal.x = mesh->mNormals[i].x;
		vertex.Normal.y = mesh->mNormals[i].y;
		vertex.Normal.z = mesh->mNormals[i].z;

		//vertex.Tangent.x = mesh->mTangents[i].x;
		//vertex.Tangent.y = mesh->mTangents[i].y;
		//vertex.Tangent.z = mesh->mTangents[i].z;
		//vertex.Tangent = glm::vec3(0.0f,0.0f, 0.0f);
		
		if (mesh->mTextureCoords[0])
		{
			vertex.Texcoord.x = mesh->mTextureCoords[0][i].x;
			vertex.Texcoord.y = mesh->mTextureCoords[0][i].y;
		}
		else
			vertex.Texcoord = glm::vec2(0.0f, 0.0f);

			vertices.push_back(vertex);
	}
	// 处理索引
	for (unsigned int i = 0; i < mesh->mNumFaces; i++)
	{
		aiFace face = mesh->mFaces[i];
		for (unsigned int j = 0; j < face.mNumIndices; j++)
			indices.push_back(face.mIndices[j]);
	}

	// 处理材质
	if (mesh->mMaterialIndex >= 0)
	{
		aiMaterial* material = scene->mMaterials[mesh->mMaterialIndex];
		std::vector<myTexture> diffuseMaps = loadMaterialTextures(material,aiTextureType_DIFFUSE, "texture_diffuse");
		textures.insert(textures.end(), diffuseMaps.begin(), diffuseMaps.end());
		std::vector<myTexture> specularMaps = loadMaterialTextures(material,aiTextureType_SPECULAR, "texture_specular");
		textures.insert(textures.end(), specularMaps.begin(), specularMaps.end());
		//std::vector<myTexture> normalMaps = loadMaterialTextures(material, aiTextureType_HEIGHT, "texture_normal");
		//textures.insert(textures.end(), normalMaps.begin(), normalMaps.end());
	}

	return Mesh(vertices, indices, textures);
}

std::vector<myTexture> Model::loadMaterialTextures(aiMaterial* mat, aiTextureType type, std::string typeName)
{
	std::vector<myTexture> textures;
	if(mat->GetTextureCount(type)>0)
	{
	for (unsigned int i = 0; i < mat->GetTextureCount(type); i++)//如果没有贴图，则这个count为0，根本没进循环
		{
			aiString str;
			mat->GetTexture(type, i, &str);
			bool skip = false;
			for (unsigned int j = 0; j < textures_loaded.size(); j++)
			{
				if (std::strcmp(textures_loaded[j].path.data, str.C_Str()) == 0)
				{
					textures.push_back(textures_loaded[j]);
					skip = true;
					break;
				}
			}
			if (!skip)
			{   // 如果纹理还没有被加载，则加载它
				myTexture texture;
				texture.slot = TextureFromFile(str.C_Str(), directory);
				texture.type = typeName;
				texture.path = str.C_Str();
				textures.push_back(texture);
				textures_loaded.push_back(texture); // 添加到已加载的纹理中
			}
		}
	}
	else
	{
		std::string path = "noise.jpg";
		aiString str = aiString(path);
		myTexture texture;
		texture.slot = TextureFromFile(str.C_Str(), directory);
		texture.type = typeName;
		
		//mat->GetTexture(type, 0, &str);
		texture.path =str.C_Str();
		textures.push_back(texture);
	}
	return textures;
}

unsigned int Model::TextureFromFile(const char* path, const std::string& directory)
{
	std::string filename = std::string(path);
	filename = directory + '/' + filename;

	unsigned int textureID;
	glGenTextures(1, &textureID);

	int width, height, nrComponents;
	unsigned char* data = stbi_load(filename.c_str(), &width, &height, &nrComponents, 0);
	if (data)
	{
		GLenum format;
		if (nrComponents == 1)
			format = GL_RED;
		else if (nrComponents == 3)
			format = GL_RGB;
		else if (nrComponents == 4)
			format = GL_RGBA;

		glBindTexture(GL_TEXTURE_2D, textureID);
		glTexImage2D(GL_TEXTURE_2D, 0, format, width, height, 0, format, GL_UNSIGNED_BYTE, data);
		glGenerateMipmap(GL_TEXTURE_2D);

		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

		stbi_image_free(data);
	}
	else
	{
		std::cout << "Texture failed to load at path: " << path << std::endl;
		stbi_image_free(data);
	}

	return textureID;
}

glm::mat4 Model::MatrixLerp(glm::mat4 x, glm::mat4 y, float t)
{
	glm::mat4 temp = t * y + (1 - t) * x;
	return temp;
}

void Model::Draw(Shader& shader)
{
	for (unsigned int i = 0; i < meshes.size(); i++)
		meshes[i].Draw(shader);
}

void Model::DrawInstanced(Shader& shader,int amount)
{
	for (unsigned int i = 0; i < meshes.size(); i++)
		meshes[i].DrawInstanced(shader,amount);
}

void Model::ResetToDefaultModelMatrix(float t)
{
	float totalTime = 0.1f;
	float weight = t / totalTime;
	mModelMatrix = MatrixLerp(mModelMatrix, defaultModelMatrix, weight);//使mModelMatrix无限趋近于defaultModelMatrix，效果很赞
}

void Model::SetModelMatrixPosition(glm::vec3 Pos)
{
	mModelMatrix = glm::translate(mModelMatrix, Pos);
}

void Model::SetModelMatrixRotation(float Radians, glm::vec3 Axis)
{
	mModelMatrix = glm::rotate(mModelMatrix, Radians, Axis);
}

void Model::SetModelMatrixScale(glm::vec3 Scale)
{
	mModelMatrix = glm::scale(mModelMatrix, Scale);
}

float Model::GetNormalizeScale(glm::vec3 MassCenter)
{
	float maxDis = 0;
	for (auto mesh : meshes) {
		for (auto vertex : mesh.vertices) {
			float dis = glm::distance(vertex.Position, MassCenter);
			maxDis = dis > maxDis ? dis : maxDis;
		}		
	}
	
	return 50.0f / maxDis;
}
