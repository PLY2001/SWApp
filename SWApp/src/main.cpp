// [Win32] Our example includes a copy of glfw3.lib pre-compiled with VS2010 to maximize ease of testing and compatibility with old VS compilers.
// To link with VS2010-era libraries, VS2015+ requires linking with legacy_stdio_definitions.lib, which we do using this pragma.
// Your own project should not be affected, as you are likely to link with a newer binary of GLFW that is adequate for your version of Visual Studio.
#if defined(_MSC_VER) && (_MSC_VER >= 1900) && !defined(IMGUI_DISABLE_WIN32_FUNCTIONS)
#pragma comment(lib, "legacy_stdio_definitions")
#endif
#include <GL/glew.h>
#include <GLFW/glfw3.h> // Will drag system OpenGL headers
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include <stdio.h>
#define GL_SILENCE_DEPRECATION
#include "Application.h"
#include <windows.h>
#include "Application.h"

#include "Shader.h"
#include "Renderer.h"
#include "Model.h"
#include "UniformBuffer.h"
#include "InstanceBuffer.h"
#include "FrameBuffer.h"
#include "Texture.h"

#include <stack> //栈

#include <Python.h>//Python API

#include "Config.h"

PyObject* pModule_predict = nullptr;
PyObject* pFunc_predict = nullptr; 
PyObject* pModule_build_dataset = nullptr;
PyObject* pFunc_build_dataset = nullptr;

MyApp::MyApplication& App = MyApp::MyApplication::GetInstance();//获取唯一的实例引用
std::unordered_map<std::string, MyApp::MyFaceFeature> faceMap;//获取面哈希表
std::map<MyApp::SWState, MyApp::MyState> swStateMap;//获取SW交互状态

enum class ViewDirection {
	FrontView, SideView, VerticalView, ObliqueView
};//视图方向：前视图，侧视图，俯视图, 斜视图
ViewDirection viewDirction = ViewDirection::FrontView;//记录当前视图方向

enum class ViewType {
	Depth, IsDatum_IsSFSymbol_AccuracySize, IsGeoTolerance_AccuracySize_hasMCM, IsDimTolerance_DimSize_AccuracySize, Diffuse
};//
ViewType viewType = ViewType::Depth;//记录当前视图类型

glm::vec3 GetRGB(MyApp::MyFaceFeature faceFeature, ViewType viewType) { //根据视图类型求出该面网格所含MBD信息对应的RGB颜色
    glm::vec3 color;
    switch (viewType)
    {
    case ViewType::IsDatum_IsSFSymbol_AccuracySize:
        for (auto annotation : faceFeature.AnnotationArray) {
            color.x = annotation.IsDatum ? 0.7f : color.x;
            color.y = annotation.IsSFSymbol ? annotation.SFSType / 10.0f : color.y;
            color.z = annotation.IsSFSymbol ? annotation.AccuracySize : color.z;
        }
	    break;
    case ViewType::IsGeoTolerance_AccuracySize_hasMCM:
		for (auto annotation : faceFeature.AnnotationArray) {
			color.x = annotation.IsGeoTolerance ? annotation.Type / 255.0f : color.x;
			color.y = annotation.IsGeoTolerance ? annotation.AccuracySize : color.y;
			color.z = annotation.IsGeoTolerance ? annotation.hasMCM * 0.7f : color.z;
		}
		break;
    case ViewType::IsDimTolerance_DimSize_AccuracySize:
		for (auto annotation : faceFeature.AnnotationArray) {
			color.x = annotation.IsDimTolerance ? annotation.Type / 255.0f : color.x;
			color.y = annotation.IsDimTolerance ? min(1.0f, annotation.DimSize / 100.0f) : color.y;
			color.z = annotation.IsDimTolerance ? annotation.AccuracySize : color.z;
		}
		break;
    default:
        break;
    }
    return color;
}

enum class CullMode {
	CullBack, CullFront
};//剔除方法
CullMode cullMode = CullMode::CullBack;//记录当前剔除方法

float deltaTime = 0;//每次循环耗时
float lastTime = 0;//上一次记录时间

//窗口尺寸
unsigned int WinWidth = 1440;// 1330;
unsigned int WinHeight = 900;// 670;
//渲染显示尺寸
unsigned int DisplayWidth = 600;
unsigned int DisplayHeight = 600;

float PictureSize = 50.0f; //正交投影取景范围大小

//照相机位置、前向、上向
glm::vec3 cameraPos[4] = { glm::vec3(0.0f, 0.0f, PictureSize + 1.0f),  glm::vec3(-PictureSize - 1.0f, 0.0f, 0.0f), glm::vec3(0.0f, PictureSize + 1.0f, 0.0f) , glm::vec3(PictureSize + 1.0f, PictureSize + 1.0f,  PictureSize + 1.0f) / 1.732f };
glm::vec3 cameraFront[4] = { glm::vec3(0.0f, 0.0f, -1.0f), glm::vec3(1.0f, 0.0f, 0.0f), glm::vec3(0.0f, -1.0f, 0.0f), glm::vec3(-1.0f, -1.0f, -1.0f), };
glm::vec3 cameraUp[4] = { glm::vec3(0.0f, 1.0f, 0.0f), glm::vec3(0.0f, 1.0f, 0.0f), glm::vec3(0.0f, 0.0f, -1.0f),  glm::vec3(0.0f, 1.0f, 0.0f) };

bool modelLoaded = false;//是否导入了模型
bool toRotate = false;//是否旋转模型

bool toTakePictures = false;//是否拍照
bool lastFileFinished = true;//上一CAD文件是否拍照完成
#define VIEWCOUNT 24
#define VIEWDIRCOUNT 3
#define VIEWTYPECOUNT 4
#define CULLMODECOUNT 2
int picturesType[VIEWCOUNT+1][3];//该表存储了每个截图（18张 + 略缩图）对应的模式（方向、类型、剔除）
int pictureIndex = 0;//截图索引

std::vector<glm::vec2> convexHull[6];//6个方向的凸包2d坐标

bool toShowConvexHull = false;//是否显示凸包

std::vector<std::string> ResultCADNameList;
std::vector<float> ResultSimList;
std::vector<std::shared_ptr<Texture>> ResultThumbnail(5);

bool toRetrivalWithMBD = true;

std::vector<std::shared_ptr<Texture>> MBDViewDatasetTextures(VIEWCOUNT);
std::vector<std::shared_ptr<Texture>> ResultMBDViewDatasetTextures(VIEWCOUNT*5);

//数据库模型总数
int datasetModelCount = 0;


std::string string_To_UTF8(const std::string& str)
{
	int nwLen = ::MultiByteToWideChar(CP_ACP, 0, str.c_str(), -1, NULL, 0);

	wchar_t* pwBuf = new wchar_t[nwLen + 1];//一定要加1，不然会出现尾巴
	ZeroMemory(pwBuf, nwLen * 2 + 2);

	::MultiByteToWideChar(CP_ACP, 0, str.c_str(), str.length(), pwBuf, nwLen);

	int nLen = ::WideCharToMultiByte(CP_UTF8, 0, pwBuf, -1, NULL, NULL, NULL, NULL);

	char* pBuf = new char[nLen + 1];
	ZeroMemory(pBuf, nLen + 1);

	::WideCharToMultiByte(CP_UTF8, 0, pwBuf, nwLen, pBuf, nLen, NULL, NULL);

	std::string retStr(pBuf);

	delete[]pwBuf;
	delete[]pBuf;

	pwBuf = NULL;
	pBuf = NULL;

	return retStr;
}


#define WIDTHBYTES(bits) (((bits)+31)/32*4)//用于使图像宽度所占字节数为4byte的倍数
bool PictureResize(unsigned char* pColorDataMid, unsigned char* pColorData, int targetWidth, int targetHeight, int width,int height) {
	int l_width = WIDTHBYTES(width * 24);//计算位图的实际宽度并确保它为4byte的倍数  
	int write_width = WIDTHBYTES(targetWidth * 24);//计算写位图的实际宽度并确保它为4byte的倍数
	for (int hnum = 0; hnum < targetHeight; hnum++) {
		for (int wnum = 0; wnum < targetWidth; wnum++)
		{
			double d_original_img_hnum = hnum * height / (double)targetHeight;
			double d_original_img_wnum = wnum * width / (double)targetWidth;
			int i_original_img_hnum = d_original_img_hnum;
			int i_original_img_wnum = d_original_img_wnum;
			double distance_to_a_x = d_original_img_wnum - i_original_img_wnum;//在原图像中与a点的水平距离  
			double distance_to_a_y = d_original_img_hnum - i_original_img_hnum;//在原图像中与a点的垂直距离  

			int original_point_a = i_original_img_hnum * l_width + i_original_img_wnum * 3;//数组位置偏移量，对应于图像的各像素点RGB的起点,相当于点A    
			int original_point_b = i_original_img_hnum * l_width + (i_original_img_wnum + 1) * 3;//数组位置偏移量，对应于图像的各像素点RGB的起点,相当于点B  
			int original_point_c = (i_original_img_hnum + 1) * l_width + i_original_img_wnum * 3;//数组位置偏移量，对应于图像的各像素点RGB的起点,相当于点C   
			int original_point_d = (i_original_img_hnum + 1) * l_width + (i_original_img_wnum + 1) * 3;//数组位置偏移量，对应于图像的各像素点RGB的起点,相当于点D   
			if (i_original_img_hnum + 1 >= width)
			{
				original_point_c = original_point_a;
				original_point_d = original_point_b;
			}
			if (i_original_img_wnum + 1 >= height)
			{
				original_point_b = original_point_a;
				original_point_d = original_point_c;
			}

			int pixel_point = hnum * write_width + wnum * 3;//映射尺度变换图像数组位置偏移量  
			for (int i = 0; i < 3; i++)
			{
				pColorDataMid[pixel_point + i] =
					pColorData[original_point_a + i] * (1 - distance_to_a_x) * (1 - distance_to_a_y) +
					pColorData[original_point_b + i] * distance_to_a_x * (1 - distance_to_a_y) +
					pColorData[original_point_c + i] * distance_to_a_y * (1 - distance_to_a_x) +
					pColorData[original_point_c + i] * distance_to_a_y * distance_to_a_x;
			}

		}
	}
	return true;
}


bool TakingPicture(GLuint framebuffer, std::string fileName, std::string filePath) { //截屏并保存
	unsigned char* picture = new unsigned char[WinWidth * WinHeight * 3];
	glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
	//glBindBuffer(GL_FRAMEBUFFER, framebuffer);
	glReadPixels(0, 0, WinWidth, WinHeight, GL_BGR, GL_UNSIGNED_BYTE, picture);
	//WriteBMP(picture, WinWidth, WinHeight);

    std::string name = filePath + fileName + "_" + std::to_string((int)viewDirction) + "_" + std::to_string((int)viewType) + "_" + std::to_string((int)cullMode) + ".bmp";
	FILE* pFile = fopen(name.c_str(), "wb");
	if (pFile) {	
		//颜色数据总尺寸：
		const int ColorBufferSize = DisplayWidth * DisplayHeight * 3;
		//文件头
		BITMAPFILEHEADER fileHeader;
		fileHeader.bfType = 0x4D42;	//0x42是'B'；0x4D是'M'
		fileHeader.bfReserved1 = 0;
		fileHeader.bfReserved2 = 0;
		fileHeader.bfSize = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER) + ColorBufferSize;
		fileHeader.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);

		//信息头
		BITMAPINFOHEADER bitmapHeader = { 0 };
		bitmapHeader.biSize = sizeof(BITMAPINFOHEADER);
		bitmapHeader.biHeight = DisplayWidth;
		bitmapHeader.biWidth = DisplayHeight;
		bitmapHeader.biPlanes = 1;
		bitmapHeader.biBitCount = 24;
		bitmapHeader.biSizeImage = ColorBufferSize;
		bitmapHeader.biCompression = 0; //BI_RGB

		//写入文件头和信息头
		fwrite(&fileHeader, sizeof(BITMAPFILEHEADER), 1, pFile);
		fwrite(&bitmapHeader, sizeof(BITMAPINFOHEADER), 1, pFile);
		//写入颜色数据
		unsigned char* final_picture = new unsigned char[DisplayWidth * DisplayHeight * 3];
		PictureResize(final_picture, picture, DisplayWidth, DisplayHeight, WinWidth, WinHeight);
		fwrite(final_picture, 1, DisplayWidth * DisplayHeight * 3, pFile);
		fwrite(final_picture, ColorBufferSize, 1, pFile);

		fclose(pFile);

	}
    else {
        return false;
    }
	glBindFramebuffer(GL_FRAMEBUFFER, 0);
	delete picture;
    return true;
}

//计算三角形面积
double TriangleAreaSize(glm::vec2 p1, glm::vec2 p2, glm::vec2 p3) {
	double S = 0.5 * glm::abs((p2.x - p1.x) * (p3.y - p1.y) - (p2.y - p1.y) * (p3.x - p1.x));
	return S;
}

//交换
void Swap(glm::vec2& p1, glm::vec2& p2) {
	glm::vec2 tmp = p2;
	p2 = p1;
	p1 = tmp;
}

//比较a,b与x轴夹角的大小
bool Compare(glm::vec2 a, glm::vec2 b)
{
	double anglea = atan2((double)a.y, (double)a.x);
	double angleb = atan2((double)b.y, (double)b.x);
	if (anglea == angleb) {//共线条件比较
		int d1 = a.x * a.x + a.y * a.y;
		int d2 = b.x * b.x + b.y * b.y;
		return d1 > d2;
	}
	else
		return anglea > angleb;
}

//二维叉乘求模
double Cross(glm::vec2 v1, glm::vec2 v2) {
	return v1.x * v2.y - v1.y * v2.x;
}

//计算夹角
double getangle(glm::vec2 p, glm::vec2 p1, glm::vec2 p2) {
	glm::vec2 v1(p2.x - p1.x, p2.y - p1.y);
	glm::vec2 v2(p.x - p1.x, p.y - p1.y);
	v2 = v2 == glm::vec2(0) ? v1 : v2;
	v1 = v1 == glm::vec2(0) ? v2 : v1;
	double theta = atan2((double)Cross(v1, v2), (double)glm::dot(v1, v2));
	return theta;
}

std::vector<glm::vec2> Graham(std::vector<glm::vec2> plist, int psize) { //有问题：得到的凸包顶点很多的时候就并非按角度排序
	//处理数据，极点至首位
	for (int i = 0; i < psize; i++)
	{
		if (plist[i].y < plist[0].y) {
			Swap(plist[i], plist[0]);
		}
	}

	glm::vec2 pole = plist[0];//坐标原点

	//将极点为坐标原点处理各点坐标
	glm::vec2 p = plist[0];
	for (int i = 0; i < psize; i++) {
		plist[i].x -= p.x;
		plist[i].y -= p.y;
	}

	//按极角排序
	for (int i = 0; i < psize - 1; i++)
		for (int j = 0; j < psize - 1 - i; j++) {
			if (Compare(plist[j], plist[j + 1]))//plist[i]<plist[i+1]
				Swap(plist[j], plist[j + 1]);
		}

	std::stack<glm::vec2> stack;
	//逆时针找凸包结点
	stack.push(plist[0]);
	stack.push(plist[1]);
	for (int i = 2; i < psize; i++) {
		glm::vec2 p1 = stack.top();
		stack.pop();
		glm::vec2 p2 = stack.top();
		stack.push(p1);
		if (Cross(stack.top(), plist[i]) < 0.000000001 && Cross(stack.top(), plist[i]) > -0.000000001 && getangle(plist[i], p1, p2) < 0) {//点在线上		
			double c = Cross(stack.top(), plist[i]);
			stack.push(plist[i]);
		}
		else if (Cross(stack.top(), plist[i]) < 0 )//在栈顶点与原点连线的右边
		{
			stack.pop();
			stack.push(plist[i]);
		}
		else {
			p1 = stack.top();
			stack.pop();
			p2 = stack.top();
			if (getangle(plist[i], p1, p2) < 0) {//负角且是钝角，保留
				stack.push(p1);
				stack.push(plist[i]);
			}
			else {//正角，舍去
				while (stack.size()>2 && getangle(plist[i], p1, p2) >= 0)
				{
					p1 = p2;
					stack.pop();
					p2 = stack.top();
				}
				stack.push(p1);
				stack.push(plist[i]);
			}
		}
	}

	int pnum = stack.size();
	//顺时针获取栈内元素
	std::vector<glm::vec2> result;
	for (int i = 0; i < pnum; i++)
	{
		result.push_back(glm::vec2(stack.top().x + pole.x, stack.top().y + pole.y));
		stack.pop();
	}

	return result;
}

glm::vec2 GetVertex2D(glm::vec3 p,int i) { //根据投影方向将vec3转vec2
	switch (i)
	{
	case 0:
		return glm::vec2(p.x, p.y);
	case 1:
		return glm::vec2(p.x, p.y);
	case 2:
		return glm::vec2(p.y, p.z);
	case 3:
		return glm::vec2(p.y, p.z);
	case 4:
		return glm::vec2(p.x, p.z);
	case 5:
		return glm::vec2(p.x, p.z);
	}
}


int MainAxisCorrection(std::unordered_map<std::string, Model>& modelMap) {
	//1.求6个方向投影后的边界点(x,y)
	BorderVertexList2D borderVertexList;
	std::map<VertexKey, int> vlist[6]; //用于查询以避免重复顶点
	for (auto model : modelMap) {
		BorderVertexList thisVertexList = model.second.GetBorderVertexList(App.GetMinBoxVertex(), App.GetMaxBoxVertex(),App.GetMassCenter());//获取该面的边界点(x,y,z)
		for (int i = 0; i < 6; i++) {
			for (auto vertex : thisVertexList.VertexList[i]) {
				VertexKey vk; //创建map的key，其中元素是glm::vec3。不能直接用glm::vec3作为key，因为需要重载<操作符以比较两个key的大小
				vk.v = glm::vec3(vertex);
				if (vlist[i].count(vk) > 0) { //如果顶点重复，跳过
					continue;
				}
				else {
					vlist[i][vk] = 1; //顶点未重复则记录
				}
				borderVertexList.VertexList[i].push_back(GetVertex2D(vertex,i));
			}
		}
	}

	//2.Graham扫描法求凸包和凸包面积
	for (int i = 0; i < 6; i++) {
		convexHull[i].clear();
		int psize = borderVertexList.VertexList[i].size();
		if (psize > 2) {
			convexHull[i] = Graham(borderVertexList.VertexList[i], psize);
		}
		else {
			convexHull[i] = borderVertexList.VertexList[i];
		}
	}
	double convexHullAreaSize[6] = { 0,0,0,0,0,0 };
	for (int i = 0; i < 6; i++) {
		double areaSize = 0;
		int chsize = convexHull[i].size();
		if (chsize > 2) {
			for (int j = 1; j < convexHull[i].size() - 1; j++) {
				areaSize += TriangleAreaSize(convexHull[i][0], convexHull[i][j], convexHull[i][j + 1]);
			}
		}		
		convexHullAreaSize[i] = areaSize;
	}

	//3.确定最大面的方向
	int maxAreaSizeIndex = -1;
	int minAreaSizeIndex = -1;
	double maxAreaSize = 0;
	double minAreaSize = convexHullAreaSize[0];
	int maxAreaCount = 0;
	for (int i = 0; i < 6; i++) {
		if (maxAreaSize < convexHullAreaSize[i]) {
			maxAreaSizeIndex = i;
			maxAreaSize = convexHullAreaSize[i];
		}
		if (minAreaSize > convexHullAreaSize[i]) {
			minAreaSizeIndex = i;
			minAreaSize = convexHullAreaSize[i];
		}
	}
	for (int i = 0; i < 6; i++) {
		maxAreaCount = ((maxAreaSize - convexHullAreaSize[i]) < 0.00001 && (maxAreaSize - convexHullAreaSize[i]) > -0.00001) ? (maxAreaCount + 1) : maxAreaCount;
	}
	if (maxAreaCount == 3 || maxAreaCount == 5) {
		int theOtherSide[6] = { 1,0,3,2,5,4 };
		maxAreaSizeIndex = theOtherSide[minAreaSizeIndex];
	}	

	return maxAreaSizeIndex;
}

//加载模型
void LoadModel(std::unordered_map<std::string, Model>& modelMap, std::unordered_map<std::string, InstanceBuffer>& instanceMap) {
	float minScale = 1e10;
	float thisScale = 1e10;
	modelMap.clear();
	for (auto face : faceMap) {
		std::string fileName = face.first + ".STL";
		std::string filePath = App.GetExportPathUtf8();
		Model model((filePath + fileName));//读取文件
		modelMap[face.first] = model;

		//尺寸归一化
		thisScale = model.GetNormalizeScale(App.GetMassCenter());//求出每个面模型的缩放尺寸
		minScale = thisScale < minScale ? thisScale : minScale;//得到最小的缩放尺寸   

	}
	int mainAxisCorrectDirIndex = MainAxisCorrection(modelMap);
	glm::vec3 correctRotateAxis[6] = { glm::vec3(1.0f, 0.0f, 0.0f), glm::vec3(-1.0f, 0.0f, 0.0f), glm::vec3(0.0f, 0.0f, 1.0f), glm::vec3(0.0f, 0.0f, -1.0f), glm::vec3(1.0f, 0.0f, 0.0f),glm::vec3(1.0f, 0.0f, 0.0f) };
	float correctRotateAngles[6] = { 90.0f,90.0f ,90.0f ,90.0f ,90.0f ,0.0f };
	//创建实例
	instanceMap.clear();
	for (auto model : modelMap) {
		//将最大面方向作为y轴反方向	
		modelMap[model.first].SetModelMatrixRotation(glm::radians(correctRotateAngles[mainAxisCorrectDirIndex]), correctRotateAxis[mainAxisCorrectDirIndex]);

		modelMap[model.first].SetModelMatrixScale(glm::vec3(minScale)); //尺寸归一化
		modelMap[model.first].SetModelMatrixPosition(-App.GetMassCenter()); //以质心置中 
		modelMap[model.first].SetDefaultModelMatrix(); //设定默认Model矩阵

		InstanceBuffer instance(sizeof(glm::mat4), &model.second.GetModelMatrix());
		instance.AddInstanceBuffermat4(model.second.meshes[0].vaID, 3);
		instanceMap[model.first] = instance;
	}
	modelLoaded = modelMap.size() > 0;
}

void LoadConvexHullModel(std::vector<Model>& convexHullModelList, std::vector<InstanceBuffer>& convexHullInstanceList, std::vector<glm::vec2>* vertexList, glm::vec3 minBoxVertex, glm::vec3 maxBoxVertex) {
	convexHullModelList.clear();
	convexHullInstanceList.clear();
	for (int i = 0; i < 6; i++) {
		if (vertexList[i].size() > 2) {
			Model model(vertexList[i], i, App.GetMinBoxVertex(), App.GetMaxBoxVertex(), App.GetMassCenter());
			convexHullModelList.push_back(model);

			InstanceBuffer instance(sizeof(glm::mat4), &model.GetModelMatrix());
			instance.AddInstanceBuffermat4(model.meshes[0].vaID, 3);
			convexHullInstanceList.push_back(instance);
		}		
	}
}

PyObject* pythonImportModule(const char* pyDir, const char* name) {
	// 引入当前路径,否则下面模块不能正常导入
	char tempPath[256] = {};
	sprintf(tempPath, "sys.path.append('%s')", pyDir);
	PyRun_SimpleString("import sys");
	PyRun_SimpleString(tempPath);
	

	// import ${name}
	PyObject* module = PyImport_ImportModule(name);
	return module;
}

int callPythonFun_s_i_i(PyObject* module, const char* a, int b, int c) {
	//获取模块字典属性
	PyObject* pDict = PyModule_GetDict(module);
	if (pDict == nullptr) {
		return 666;
	}

	//直接获取模块中的函数
	PyObject* pFunc = PyDict_GetItemString(pDict, "main");
	if (pFunc == nullptr) {
		return 666;
	}

	// 构造python 函数入参， 接收2
	PyObject* pArgs = PyTuple_New(3);
	PyTuple_SetItem(pArgs, 0, Py_BuildValue("s", a));
	PyTuple_SetItem(pArgs, 1, Py_BuildValue("i", b));
	PyTuple_SetItem(pArgs, 2, Py_BuildValue("i", c));

	//调用函数，并得到 python 类型的返回值
	PyObject* result = PyEval_CallObject(pFunc, pArgs);

	int ret = 0;
	//将python类型的返回值转换为c/c++类型
	PyArg_Parse(result, "i", &ret);
	return ret;
}

int callPythonFun(PyObject* module) {
	//获取模块字典属性
	PyObject* pDict = PyModule_GetDict(module);
	if (pDict == nullptr) {
		return 666;
	}

	//直接获取模块中的函数
	PyObject* pFunc = PyDict_GetItemString(pDict, "main");
	if (pFunc == nullptr) {
		return 666;
	}

	//调用函数，并得到 python 类型的返回值
	PyObject* result = PyEval_CallObject(pFunc, NULL);

	int ret = 0;
	//将python类型的返回值转换为c/c++类型
	PyArg_Parse(result, "i", &ret);
	return ret;
}


bool InitialPython() {
	//python 初始化
	std::string str = App.GetPythonHome();
	wchar_t*  wc = new wchar_t[str.size()];
	swprintf(wc, 100, L"%S", str.c_str()); //注意大写
	Py_SetPythonHome(wc);
	Py_Initialize();
	if (!Py_IsInitialized())
	{
		return false;
	}
	else
	{
		pModule_predict = pythonImportModule(App.GetPythonProjectPath().c_str(),"predict_c++");
		pModule_build_dataset = pythonImportModule(App.GetPythonProjectPath().c_str(),"build_dataset_c++");
		//pModule_predict = pythonImportModule(App.GetPythonProjectPath().c_str(),"gg");
		if (pModule_predict == NULL || pModule_build_dataset == NULL) {
			return false;
		}
		else
		{
			return true;
		}
	}
}

bool LoadFileInDatasetForResult(std::string path, std::string CADName, int index)
{
	bool result = false;
	int viewCount = index*VIEWCOUNT;
	//std::vector <std::string> fileNames;
	//文件句柄
	intptr_t hFile = 0;
	//文件信息
	struct _finddata_t fileinfo;
	std::string p;
	if ((hFile = _findfirst(p.assign(path).append("*").c_str(), &fileinfo)) != -1)
	{
		do
		{
			//如果不是目录或者隐藏文件
			if (!(fileinfo.attrib & _A_SUBDIR || fileinfo.attrib & _A_HIDDEN))
			{
				std::string textstr = fileinfo.name;
				std::regex pattern(CADName + "_");	//只保留文件名，不保留后缀
				std::string::const_iterator iter_begin = textstr.cbegin();
				std::string::const_iterator iter_end = textstr.cend();
				std::smatch matchResult;
				if (std::regex_search(iter_begin, iter_end, matchResult, pattern)) {
					ResultMBDViewDatasetTextures[viewCount].reset(new Texture(path + textstr));
					viewCount++;
					//fileNames.push_back(matchResult.prefix());	

				}

			}
		} while (_findnext(hFile, &fileinfo) == 0);
		_findclose(hFile);
	}
	if (viewCount == VIEWCOUNT * 5) {
		result = true;
	}
	return result;
}

bool ReadResults() {
	ResultCADNameList.clear();
	ResultSimList.clear();
	std::ifstream source(App.GetPythonProjectPath() + "/Results/FileNameList.json");
	std::string line;
	while (getline(source, line)) {
		if (line == "[" || line == "]") {
			continue;
		}
		else {
			if (line.back() == ',') {
				ResultCADNameList.push_back(line.substr(1, line.size() - 8));
			}
			else {
				ResultCADNameList.push_back(line.substr(1, line.size() - 7));
			}
		}
	}

	std::ifstream source1(App.GetPythonProjectPath() + "/Results/SimList.json");
	std::string line1;
	while (getline(source1, line1))
	{
		if (line1 == "[" || line1 == "]") {
			continue;
		}
		else {
			if (line1.back() == ',') {
				float Sim;
				std::istringstream str1(line1.substr(0, line1.size() - 2));
				str1 >> Sim;
				ResultSimList.push_back(Sim);
			}
			else {
				float Sim;
				std::istringstream str1(line1.substr(0, line1.size() - 1));
				str1 >> Sim;
				ResultSimList.push_back(Sim);
			}
		}

	}
	if (ResultCADNameList.size() > 0) {
		for (int i = 0; i < ResultCADNameList.size(); i++)
		{
			ResultThumbnail[i].reset(new Texture(App.GetModelPictureExportPath() + ResultCADNameList[i] + "_.bmp"));
			LoadFileInDatasetForResult(App.GetPictureExportPath(true), ResultCADNameList[i], i);
		}
		return true;
	}	
	else {
		return false;
	}

	
}

int GetModelCountInDataset(std::string path)
{
	int count = 0;
	//文件句柄
	intptr_t hFile = 0;
	//文件信息
	struct _finddata_t fileinfo;
	std::string p;
	if ((hFile = _findfirst(p.assign(path).append("*").c_str(), &fileinfo)) != -1)
	{
		do
		{
			//如果不是目录或者隐藏文件
			if (!(fileinfo.attrib & _A_SUBDIR || fileinfo.attrib & _A_HIDDEN))
			{
				count++;
			}
		} while (_findnext(hFile, &fileinfo) == 0);
		_findclose(hFile);
	}
	return count;
}

bool Retrival() {
	int result = 0;
	if (datasetModelCount == GetModelCountInDataset(App.GetPictureExportPath(true))/VIEWCOUNT) {
		result = callPythonFun_s_i_i(pModule_predict, App.GetCADNameUtf8().c_str(), (int)toRetrivalWithMBD, datasetModelCount);
	}
	else {
		return false;
	}
	if (result == 1) {
		if (ReadResults()) {
			return true;
		}
	}
	else
		return false;
}

int BuildDataset() {
	int result = callPythonFun(pModule_build_dataset);
	return result;
}

std::string SaveThumbnail(std::string path) {
	CString modelPicturePath;
	std::string modelPicturePathStr = path + App.GetCADName() + "_.bmp";
	modelPicturePath = CA2T(modelPicturePathStr.c_str());
	if (App.SaveBitmapToFile(App.GetThumbnailEx(), modelPicturePath))
		return modelPicturePathStr;
	else
		return "";
}

bool LoadFileInDataset(std::string path,std::string CADName)
{
	bool result = false;
	int viewCount = 0;
	//std::vector <std::string> fileNames;
	//文件句柄
	intptr_t hFile = 0;
	//文件信息
	struct _finddata_t fileinfo;
	std::string p;
	if ((hFile = _findfirst(p.assign(path).append("*").c_str(), &fileinfo)) != -1)
	{
		do
		{
			//如果不是目录或者隐藏文件
			if (!(fileinfo.attrib & _A_SUBDIR || fileinfo.attrib & _A_HIDDEN))
			{
				std::string textstr = fileinfo.name;
				std::regex pattern(CADName+"_");	//只保留文件名，不保留后缀
				std::string::const_iterator iter_begin = textstr.cbegin();
				std::string::const_iterator iter_end = textstr.cend();
				std::smatch matchResult;
				if (std::regex_search(iter_begin, iter_end, matchResult, pattern)) {					
					MBDViewDatasetTextures[viewCount].reset(new Texture(path + textstr));
					viewCount++;
					//fileNames.push_back(matchResult.prefix());	
					
				}

			}
		} while (_findnext(hFile, &fileinfo) == 0);
		_findclose(hFile);
	}
	if (viewCount == VIEWCOUNT) {
		result = true;
	}
	return result;
}


bool LoadAllData(std::unordered_map<std::string, Model>& modelMap, std::unordered_map<std::string, InstanceBuffer>& instanceMap, std::vector<Model>& convexHullModelList, std::vector<InstanceBuffer>& convexHullInstanceList) {
	bool result = false;
	//2.读取属性
	result = App.StartReadProperty();
	if (!result)
		return false;
	//3.加载质量
	result = App.StartReadMassProperty();
	if (!result)
		return false;
	//4.读取MBD特征及其标注
	result = App.StartReadMBD();
	if (!result)
		return false;
	faceMap = App.GetFaceMap();
	//5.加载模型
	App.StartLoadModel();
	if (!result)
		return false;
	LoadModel(modelMap, instanceMap);
	LoadConvexHullModel(convexHullModelList, convexHullInstanceList, convexHull, App.GetMinBoxVertex(), App.GetMaxBoxVertex());
	return true;
}

void ReadPathSetting() {
	// 打开一个写文件流指向 config.ini 文件
	std::string strConfigFileName("config.ini");
	Config config(strConfigFileName);
	if (config.FileExist("config.ini"))
	{
		// 读取键值
		std::string strValue;
		if(config.KeyExists("CADPath")) 
		{
			strValue = config.Read<std::string>("CADPath");
			App.SetCADPath(strValue);
		}
		if (config.KeyExists("CADTempPath"))
		{
			strValue = config.Read<std::string>("CADTempPath");
			App.SetCADTempPath(strValue);
		}
		if (config.KeyExists("PictureExportPathForMBD"))
		{
			strValue = config.Read<std::string>("PictureExportPathForMBD");
			App.SetPictureExportPathForMBD(strValue);
		}
		if (config.KeyExists("PictureExportPathFornoMBD"))
		{
			strValue = config.Read<std::string>("PictureExportPathFornoMBD");
			App.SetPictureExportPathFornoMBD(strValue);
		}
		if (config.KeyExists("ModelPictureExportPath"))
		{
			strValue = config.Read<std::string>("ModelPictureExportPath");
			App.SetModelPictureExportPath(strValue);
		}
		if (config.KeyExists("PythonHome"))
		{
			strValue = config.Read<std::string>("PythonHome");
			App.SetPythonHome(strValue);
		}
		if (config.KeyExists("PythonProjectPath"))
		{
			strValue = config.Read<std::string>("PythonProjectPath");
			App.SetPythonProjectPath(strValue);
		}
	}
}




// Main code
#ifdef DEBUG
int main(int, char**)
#else
int WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
#endif
{
    //glfw初始化
    if (!glfwInit())
        return 1;
    const char* glsl_version = "#version 130";
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 0);
    glfwWindowHint(GLFW_SAMPLES, 8);//设置MSAAx8
    glEnable(GL_MULTISAMPLE);//开启MSAA

    //创建窗口上下文
    GLFWwindow* window = glfwCreateWindow(WinWidth, WinHeight, "SWApp", nullptr, nullptr);
    if (window == nullptr) {
        glfwTerminate();
        return 1;
    }       
    glfwMakeContextCurrent(window);
    glfwSwapInterval(0); //1=开启垂直同步

	//LONG_PTR exst = ::GetWindowLongPtr(Handle, GWL_EXSTYLE);
	//::SetWindowLongPtr(Handle, GWL_EXSTYLE, exst | WS_EX_ACCEPTFILES);

    //glew初始化
	if (glewInit())
	{
		return 1;
	}
    

    //初始化ImGui
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO(); (void)io;
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;     // Enable Keyboard Controls
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad;      // Enable Gamepad Controls
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;         // Enable Docking
    io.ConfigFlags |= ImGuiConfigFlags_ViewportsEnable;       // Enable Multi-Viewport / Platform Windows
    io.Fonts->AddFontFromFileTTF("res/fonts/msyh.ttc", 20.0f, nullptr, io.Fonts->GetGlyphRangesChineseFull());//中文字体
    // Setup Dear ImGui style
    ImGui::StyleColorsLight();
    // When viewports are enabled we tweak WindowRounding/WindowBg so platform windows can look identical to regular ones.
    ImGuiStyle& style = ImGui::GetStyle();
    if (io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable) {
        style.WindowRounding = 0.0f;
        style.Colors[ImGuiCol_WindowBg].w = 1.0f;
    }
    // Setup Platform/Renderer backends
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init(glsl_version);

	ImVec4* colors = ImGui::GetStyle().Colors;
	colors[ImGuiCol_Text] = ImVec4(0.00f, 0.00f, 0.00f, 1.00f);
	colors[ImGuiCol_TextDisabled] = ImVec4(0.60f, 0.60f, 0.60f, 1.00f);
	colors[ImGuiCol_WindowBg] = ImVec4(0.95f, 0.95f, 0.97f, 1.00f);
	colors[ImGuiCol_ChildBg] = ImVec4(0.00f, 0.00f, 0.00f, 0.00f);
	colors[ImGuiCol_PopupBg] = ImVec4(0.95f, 0.95f, 0.95f, 1.00f);
	colors[ImGuiCol_Border] = ImVec4(0.90f, 0.90f, 0.90f, 1.00f);
	colors[ImGuiCol_BorderShadow] = ImVec4(0.00f, 0.00f, 0.00f, 0.00f);
	colors[ImGuiCol_FrameBg] = ImVec4(0.73f, 0.73f, 0.71f, 0.39f);
	colors[ImGuiCol_FrameBgHovered] = ImVec4(0.20f, 0.78f, 0.35f, 0.59f);
	colors[ImGuiCol_FrameBgActive] = ImVec4(0.20f, 0.78f, 0.35f, 1.00f);
	colors[ImGuiCol_TitleBg] = ImVec4(0.98f, 0.98f, 0.99f, 1.00f);
	colors[ImGuiCol_TitleBgActive] = ImVec4(0.98f, 0.98f, 0.99f, 1.00f);
	colors[ImGuiCol_TitleBgCollapsed] = ImVec4(0.95f, 0.95f, 0.97f, 1.00f);
	colors[ImGuiCol_MenuBarBg] = ImVec4(0.95f, 0.95f, 0.95f, 1.00f);
	colors[ImGuiCol_ScrollbarBg] = ImVec4(0.95f, 0.95f, 0.97f, 1.00f);
	colors[ImGuiCol_ScrollbarGrab] = ImVec4(0.73f, 0.73f, 0.75f, 1.00f);
	colors[ImGuiCol_ScrollbarGrabHovered] = ImVec4(0.73f, 0.73f, 0.75f, 1.00f);
	colors[ImGuiCol_ScrollbarGrabActive] = ImVec4(0.73f, 0.73f, 0.75f, 1.00f);
	colors[ImGuiCol_CheckMark] = ImVec4(1.00f, 1.00f, 1.00f, 1.00f);
	colors[ImGuiCol_SliderGrab] = ImVec4(1.00f, 1.00f, 1.00f, 0.78f);
	colors[ImGuiCol_SliderGrabActive] = ImVec4(0.46f, 0.54f, 0.80f, 0.60f);
	colors[ImGuiCol_Button] = ImVec4(0.73f, 0.73f, 0.71f, 0.39f);
	colors[ImGuiCol_ButtonHovered] = ImVec4(0.54f, 0.76f, 1.00f, 1.00f);
	colors[ImGuiCol_ButtonActive] = ImVec4(0.41f, 0.71f, 1.00f, 1.00f);
	colors[ImGuiCol_Header] = ImVec4(0.73f, 0.73f, 0.75f, 0.31f);
	colors[ImGuiCol_HeaderHovered] = ImVec4(0.73f, 0.73f, 0.75f, 0.59f);
	colors[ImGuiCol_HeaderActive] = ImVec4(0.73f, 0.73f, 0.75f, 1.00f);
	colors[ImGuiCol_Separator] = ImVec4(0.66f, 0.66f, 0.68f, 1.00f);
	colors[ImGuiCol_SeparatorHovered] = ImVec4(0.14f, 0.44f, 0.80f, 0.78f);
	colors[ImGuiCol_SeparatorActive] = ImVec4(0.14f, 0.44f, 0.80f, 1.00f);
	colors[ImGuiCol_ResizeGrip] = ImVec4(0.35f, 0.35f, 0.35f, 0.17f);
	colors[ImGuiCol_ResizeGripHovered] = ImVec4(0.26f, 0.59f, 0.98f, 0.67f);
	colors[ImGuiCol_ResizeGripActive] = ImVec4(0.26f, 0.59f, 0.98f, 0.95f);
	colors[ImGuiCol_Tab] = ImVec4(0.88f, 0.88f, 0.90f, 1.00f);
	colors[ImGuiCol_TabHovered] = ImVec4(0.95f, 0.95f, 0.97f, 1.00f);
	colors[ImGuiCol_TabActive] = ImVec4(0.95f, 0.95f, 0.97f, 1.00f);
	colors[ImGuiCol_TabUnfocused] = ImVec4(0.88f, 0.88f, 0.90f, 1.00f);
	colors[ImGuiCol_TabUnfocusedActive] = ImVec4(0.95f, 0.95f, 0.97f, 1.00f);
	colors[ImGuiCol_DockingPreview] = ImVec4(0.26f, 0.59f, 0.98f, 0.22f);
	colors[ImGuiCol_DockingEmptyBg] = ImVec4(0.20f, 0.20f, 0.20f, 1.00f);
	colors[ImGuiCol_PlotLines] = ImVec4(0.39f, 0.39f, 0.39f, 1.00f);
	colors[ImGuiCol_PlotLinesHovered] = ImVec4(1.00f, 0.43f, 0.35f, 1.00f);
	colors[ImGuiCol_PlotHistogram] = ImVec4(0.90f, 0.70f, 0.00f, 1.00f);
	colors[ImGuiCol_PlotHistogramHovered] = ImVec4(1.00f, 0.45f, 0.00f, 1.00f);
	colors[ImGuiCol_TableHeaderBg] = ImVec4(0.78f, 0.87f, 0.98f, 1.00f);
	colors[ImGuiCol_TableBorderStrong] = ImVec4(0.57f, 0.57f, 0.64f, 1.00f);
	colors[ImGuiCol_TableBorderLight] = ImVec4(0.68f, 0.68f, 0.74f, 1.00f);
	colors[ImGuiCol_TableRowBg] = ImVec4(0.00f, 0.00f, 0.00f, 0.00f);
	colors[ImGuiCol_TableRowBgAlt] = ImVec4(0.30f, 0.30f, 0.30f, 0.09f);
	colors[ImGuiCol_TextSelectedBg] = ImVec4(0.26f, 0.59f, 0.98f, 0.35f);
	colors[ImGuiCol_DragDropTarget] = ImVec4(0.26f, 0.59f, 0.98f, 0.95f);
	colors[ImGuiCol_NavHighlight] = ImVec4(0.26f, 0.59f, 0.98f, 0.80f);
	colors[ImGuiCol_NavWindowingHighlight] = ImVec4(0.70f, 0.70f, 0.70f, 0.70f);
	colors[ImGuiCol_NavWindowingDimBg] = ImVec4(0.20f, 0.20f, 0.20f, 0.20f);
	colors[ImGuiCol_ModalWindowDimBg] = ImVec4(0.20f, 0.20f, 0.20f, 0.35f);

	style.FrameRounding = 5.0f;
	style.FrameBorderSize = 1.0f;
	style.WindowRounding = 5.0f;
	style.PopupRounding = 5.0f;
	style.FramePadding = ImVec2(6.0f, 6.0f);
	style.WindowMenuButtonPosition = 1;

	//读取config文件
	ReadPathSetting();
	//初始化python
	InitialPython();

	//是否成功检索
	bool retrivalSucessful = false;
	//是否检索
	bool isRetrival = false;

	//当前渲染的是否是mbd视图
	bool isMBDView = true;

	datasetModelCount = GetModelCountInDataset(App.GetPictureExportPath(true))/VIEWCOUNT;//数据库模型数量初始化

	bool hasMBDViewDataset = false;//当前模型是否有MBD视图数据库


	//模型哈希表(毫米)
	std::unordered_map<std::string, Model> modelMap;

	//凸包
	std::vector<Model> convexHullModelList;

    //实例哈希表
    std::unordered_map<std::string, InstanceBuffer> instanceMap;

	//凸包实例
	std::vector<InstanceBuffer> convexHullInstanceList;

	//创建变换矩阵
    glm::mat4 modelMatrix;
	glm::mat4 viewMatrix;
	glm::mat4 projectionMatrix;
	
    //Shader
    Shader shader("res/shaders/Basic.shader");
	shader.Bind();
	shader.Unbind();

	Shader convexHullShader("res/shaders/ConvexHull.shader");
	convexHullShader.Bind();
	convexHullShader.Unbind();

	FrameBuffer display(WinWidth, WinHeight);
	display.GenTexture2D();

	std::shared_ptr<Texture> thumbnail;
	std::vector<std::shared_ptr<Texture>> MBDViews;

	bool shouldAutomatizationForOneModel = false;

	//渲染方面的API
	Renderer renderer;

	//创建Uniform缓冲对象
	UniformBuffer ubo(2 * sizeof(glm::mat4), 0);
	std::vector<int> shaderIDs;
	shaderIDs.push_back(shader.RendererID);
	shaderIDs.push_back(convexHullShader.RendererID);
    ubo.Bind(shaderIDs, "Matrices");

    //初始化截图模式表
    int tempIndex = 0;
	for (int i = 0; i < VIEWDIRCOUNT; i++) { //视图方向
		for (int j = 0; j < VIEWTYPECOUNT; j++) { //视图类型
			for (int k = 0; k < CULLMODECOUNT; k++) { //剔除方向
				picturesType[tempIndex][0] = i;
				picturesType[tempIndex][1] = j;
				picturesType[tempIndex][2] = k;
                tempIndex++;
			}
		}
	}
    picturesType[VIEWCOUNT][0] = VIEWDIRCOUNT;
    picturesType[VIEWCOUNT][1] = VIEWTYPECOUNT;
    picturesType[VIEWCOUNT][2] = 0;

    //主循环
    while (!glfwWindowShouldClose(window))
    {

        if (App.ShouldAutomatization() && lastFileFinished) {     //自动化读取文件
			toRotate = false;
			toShowConvexHull = false;
			std::string name = App.GetNextToOpenFileName();
            if (name != "") {
				bool result = false;
				//1.打开文件
				result = App.StartOpenFile(name);
				//2.加载全部数据
				if(result)
					result = LoadAllData(modelMap, instanceMap, convexHullModelList, convexHullInstanceList);
				//3.准许拍照
				if(result) {
					toTakePictures = true;
					pictureIndex = 0;
					lastFileFinished = false;
					//4.保存略缩图
					SaveThumbnail(App.GetModelPictureExportPath());
				}
				if (!result) {
					toTakePictures = false;
					isMBDView = true;
					lastFileFinished = true;//换下一CAD文件
				}
            }
            else {
                App.StopAutomatization();//如果文件读取完毕就停止自动化
				datasetModelCount = BuildDataset();//运行BuildDataset.py
            }
            
        }
		if (shouldAutomatizationForOneModel&&lastFileFinished) {
			bool result = false;
			if (swStateMap[MyApp::SWState::ModelLoaded] != MyApp::MyState::Succeed) {
				//1.加载全部数据
				result = LoadAllData(modelMap, instanceMap, convexHullModelList, convexHullInstanceList);
			}
			else
			{
				result = true;
			}
			if(result)
			{
				//2.拍照
				toTakePictures = true;
				pictureIndex = 0;
				lastFileFinished = false;
				//3.保存略缩图
				SaveThumbnail(App.GetModelPictureExportPath());
			}
			else {
				toTakePictures = false;
				isMBDView = true;
				lastFileFinished = true;
				shouldAutomatizationForOneModel = false;				
			}
		}

		//设定拍照模式
		if (toTakePictures) {
			if (pictureIndex > VIEWCOUNT - 1) {
				isMBDView = false;
			}
			if (pictureIndex < VIEWCOUNT*2) {
				int index = pictureIndex % VIEWCOUNT;
				viewDirction = (ViewDirection)(picturesType[index][0]);
				viewType = (ViewType)(picturesType[index][1]);
				cullMode = (CullMode)(picturesType[index][2]);
			}
			else if (pictureIndex == VIEWCOUNT * 2) {
				viewDirction = (ViewDirection)(picturesType[VIEWCOUNT][0]);
				viewType = (ViewType)(picturesType[VIEWCOUNT][1]);
				cullMode = (CullMode)(picturesType[VIEWCOUNT][2]);
			}
			else {
				toTakePictures = false;
				isMBDView = true;
				lastFileFinished = true;//18张截图拍完后说明要换下一CAD文件
				hasMBDViewDataset = LoadFileInDataset(App.GetPictureExportPath(true), App.GetCADName());
				if (shouldAutomatizationForOneModel) {
					datasetModelCount = BuildDataset();//运行BuildDataset.py
					shouldAutomatizationForOneModel = false;
				}
			}
		}

        //更新哈希表
        faceMap = App.GetFaceMap();
        swStateMap = App.GetSWStateMap();

        //模型、实例预处理
        if (swStateMap[MyApp::SWState::ModelLoaded] != MyApp::MyState::Succeed) {//重新读取文件时需要重新加载模型
            modelLoaded = false;
        }
        if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed && modelLoaded == false) {
            //加载模型
            LoadModel(modelMap, instanceMap); 
			//凸包
			LoadConvexHullModel(convexHullModelList, convexHullInstanceList, convexHull, App.GetMinBoxVertex(), App.GetMaxBoxVertex());
        }

        //1.渲染模型	
		GLClearError();//清除错误信息

		//记录每帧的时间
		deltaTime = (float)glfwGetTime() - lastTime;
		lastTime = (float)glfwGetTime();

		//更新相机位置
		cameraPos[0] = glm::vec3(0.0f, 0.0f, PictureSize + 1.0f);
		cameraPos[1] = glm::vec3(-PictureSize - 1.0f, 0.0f, 0.0f);
		cameraPos[2] = glm::vec3(0.0f, PictureSize + 1.0f, 0.0f);

		//设置变换矩阵			
		//modelMatrix = glm::rotate(modelMatrix, deltaTime * glm::radians(50.0f), glm::vec3(0.0f, 1.0f, 0.0f));//旋转		
		viewMatrix = glm::lookAt(cameraPos[(int)viewDirction], cameraPos[(int)viewDirction] + cameraFront[(int)viewDirction], cameraUp[(int)viewDirction]);
		projectionMatrix = glm::ortho(-PictureSize, PictureSize, -PictureSize, PictureSize, 0.1f, PictureSize * 2.0f);

		//将model矩阵数组填入实例哈希表
        if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed) {
            for (auto instance : instanceMap) {
                //旋转
                if (toRotate) {
					modelMap[instance.first].SetModelMatrixPosition(App.GetMassCenter());
					modelMap[instance.first].SetModelMatrixRotation(deltaTime * glm::radians(50.0f), glm::vec3(0.0f, 1.0f, 0.0f));
					modelMap[instance.first].SetModelMatrixPosition(-App.GetMassCenter());
                }
                else {
                    modelMap[instance.first].ResetToDefaultModelMatrix(deltaTime);//回到默认Model矩阵
                }
                modelMatrix = modelMap[instance.first].GetModelMatrix();
                instance.second.SetDatamat4(sizeof(glm::mat4), &modelMatrix);
            }
			for (auto instance : convexHullInstanceList) {
				//modelMatrix = glm::scale(modelMatrix, glm::vec3(1.1f));
				instance.SetDatamat4(sizeof(glm::mat4), &modelMatrix);
			}

			
        }
		//向uniform缓冲对象填入view、projection矩阵数据
		ubo.SetDatamat4(0, sizeof(glm::mat4), &viewMatrix);
		ubo.SetDatamat4(sizeof(glm::mat4), sizeof(glm::mat4), &projectionMatrix);

		//pass
		display.Bind();//framebuffer
		glEnable(GL_DEPTH_TEST);
		renderer.ClearColor(1.0f, 1.0f, 1.0f, 1.0f);
		renderer.ClearDepth();
		renderer.CullFace((int)cullMode);

		shader.Bind();
		if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed) {
			for (auto model : modelMap) {
                ViewType tempViewType = isMBDView ? viewType : ViewType::Diffuse;
                glm::vec3 MBDColor = GetRGB(faceMap[model.first], tempViewType);
                shader.SetUniform3f("MBDColor", MBDColor.x, MBDColor.y, MBDColor.z);
                shader.SetUniform1i("viewType", (int)tempViewType);
				model.second.DrawInstanced(shader, 1);
			}
		}
		shader.Unbind();

		if(toShowConvexHull)
		{
			glDisable(GL_CULL_FACE);
			glEnable(GL_BLEND);
			glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
			convexHullShader.Bind();
			if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed) {
				for (auto model : convexHullModelList) {
					model.DrawInstanced(convexHullShader, 1);
				}
			}
			convexHullShader.Unbind();
			glDisable(GL_BLEND);
		}
		display.Unbind();//framebuffer

        //2.渲染ImGui界面
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        //MyApp		
		App.ShowMyApp();

		ImGui::Begin("显示");
		ImGui::Image((GLuint*)display.GetTexID(), ImVec2(DisplayWidth, DisplayHeight), ImVec2(0, 1), ImVec2(1, 0), ImVec4(1.0f, 1.0f, 1.0f, 1.0f), ImVec4(1.0f, 1.0f, 1.0f, 0.5f));
		ImGui::Checkbox("旋转?", &toRotate);
		ImGui::SameLine();
		ImGui::Checkbox("显示凸包?", &toShowConvexHull);
		ImGui::Separator();
		//正交投影取景框大小
		//ImGui::DragFloat("取景框大小", &PictureSize, 0.1f);
		//视图方向选择
		ImGui::RadioButton("正视图", (int*)&viewDirction, (int)ViewDirection::FrontView);
		ImGui::SameLine();
		ImGui::RadioButton("侧视图", (int*)&viewDirction, (int)ViewDirection::SideView);
		ImGui::SameLine();
		ImGui::RadioButton("俯视图", (int*)&viewDirction, (int)ViewDirection::VerticalView);
		ImGui::SameLine();
		ImGui::RadioButton("斜视图", (int*)&viewDirction, (int)ViewDirection::ObliqueView);
		ImGui::Separator();
		//视图类型
		ImGui::RadioButton("深度", (int*)&viewType, (int)ViewType::Depth);
		ImGui::SameLine();
		ImGui::RadioButton("基准_粗糙度_粗糙度值", (int*)&viewType, (int)ViewType::IsDatum_IsSFSymbol_AccuracySize);
		ImGui::SameLine();
		ImGui::RadioButton("形位公差_公差值_实体状态", (int*)&viewType, (int)ViewType::IsGeoTolerance_AccuracySize_hasMCM);
		ImGui::RadioButton("尺寸公差_尺寸值_公差值", (int*)&viewType, (int)ViewType::IsDimTolerance_DimSize_AccuracySize);
		ImGui::SameLine();
		ImGui::RadioButton("漫反射", (int*)&viewType, (int)ViewType::Diffuse);
		ImGui::Separator();
		//剔除模式选择
		ImGui::RadioButton("剔除反面", (int*)&cullMode, (int)CullMode::CullBack);
		ImGui::SameLine();
		ImGui::RadioButton("剔除正面", (int*)&cullMode, (int)CullMode::CullFront);
		ImGui::Separator();
		ImGui::End();		

        ImGui::Begin("Debug");
        //获取OpenGL错误信息	
		ImGui::Text(("OpenGL: " + std::to_string(GLCheckError())).c_str());
        //截图
		if (ImGui::Button("保存视图")) {
			TakingPicture(display.GetTexID(), App.GetCADName(), App.GetExportPath());
		}
        //耗时显示
        ImGui::Text("MBD读取总耗时=%f", (float)App.allTime);
        ImGui::Text("特征读取耗时(包含标注、面耗时)=%f", (float)App.feTime);
        ImGui::Text("标注读取耗时=%f", (float)App.aTime);
        ImGui::Text("面读取循环耗时=%f", (float)App.fTime);
        ImGui::Text("表面粗糙度读取耗时=%f", (float)App.swaTime);
        ImGui::Text("非MBD面读取耗时=%f", (float)App.bTime);
        ImGui::End();


		ImGui::Begin("三维检索");
		//加载略缩图
		if (App.ShouldLoadThumbnail()) {
			std::string modelPicturePathStr = SaveThumbnail(App.GetCADTempPath());
			thumbnail.reset(new Texture(modelPicturePathStr));
			hasMBDViewDataset = LoadFileInDataset(App.GetPictureExportPath(true), App.GetCADName());
			App.StopLoadThumbnail();
		}
		if (thumbnail) {			
			ImGui::Text("【检索目标】");
			ImGui::SameLine();
			ImGui::Text(App.GetCADNameUtf8().c_str());
			ImGui::SameLine();		
			if (ImGui::Button("加入模型特征库")) {
				shouldAutomatizationForOneModel = true;
			}
			ImGui::SameLine();
			if (hasMBDViewDataset) {
				ImGui::Text("已加入");
			}
			else {
				ImGui::Text("未加入");
			}
			ImGui::Image((GLuint*)thumbnail->GetID(), ImVec2(thumbnail->GetWidth() / 20.0f, thumbnail->GetHeight() / 20.0f), ImVec2(0, 0), ImVec2(1, 1), ImVec4(1.0f, 1.0f, 1.0f, 1.0f), ImVec4(0.0f, 0.0f, 0.0f, 0.5f));
			if(hasMBDViewDataset)
			{
				ImGui::SameLine();
				ImGui::BeginGroup();
				ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(1.0f, 1.0f));
				for (int i = 0; i < VIEWCOUNT; i++) {
					ImGui::Image((GLuint*)MBDViewDatasetTextures[i]->GetID(), ImVec2(thumbnail->GetHeight() / 60.0f, thumbnail->GetHeight() / 60.0f), ImVec2(0, 0), ImVec2(1, 1), ImVec4(1.0f, 1.0f, 1.0f, 1.0f), ImVec4(0.0f, 0.0f, 0.0f, 0.0f));
					if ((i + 1) % (VIEWCOUNT / 3) == 0) {
						continue;
					}
					ImGui::SameLine();
				}
				ImGui::PopStyleVar();
				ImGui::EndGroup();
			}
			if (ImGui::Button("检索")) {
				retrivalSucessful = Retrival();
				isRetrival = true;
			}
			ImGui::SameLine();
			ImGui::Checkbox("含MBD语义?", &toRetrivalWithMBD);
			if (retrivalSucessful) {
				ImGui::Separator();
				for (int i = 0; i < ResultCADNameList.size(); i++) {
					std::string title = "检索结果 " + std::to_string(i + 1) ;
					if (ImGui::Button(title.c_str())) {
						App.StartOpenFileFromButton(ResultCADNameList[i]);
					}
					//ImGui::Text(title.c_str());
					ImGui::SameLine();
					ImGui::Text(string_To_UTF8(ResultCADNameList[i]).c_str());
					ImGui::SameLine();
					ImGui::Text("相似度:%.2f％", ResultSimList[i] * 100.0f);
					ImGui::Image((GLuint*)ResultThumbnail[i]->GetID(), ImVec2(ResultThumbnail[i]->GetWidth() / 20.0f, ResultThumbnail[i]->GetHeight() / 20.0f), ImVec2(0, 0), ImVec2(1, 1), ImVec4(1.0f, 1.0f, 1.0f, 1.0f), ImVec4(0.0f, 0.0f, 0.0f, 0.5f));				
					ImGui::SameLine();
					ImGui::BeginGroup();
					ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(1.0f, 1.0f));
					for (int j = 0; j < VIEWCOUNT; j++) {
						ImGui::Image((GLuint*)ResultMBDViewDatasetTextures[j+i*VIEWCOUNT]->GetID(), ImVec2(thumbnail->GetHeight() / 60.0f, thumbnail->GetHeight() / 60.0f), ImVec2(0, 0), ImVec2(1, 1), ImVec4(1.0f, 1.0f, 1.0f, 1.0f), ImVec4(0.0f, 0.0f, 0.0f, 0.0f));
						if ((j + 1) % (VIEWCOUNT / 3) == 0) {
							continue;
						}
						ImGui::SameLine();
					}
					ImGui::PopStyleVar();
					ImGui::EndGroup();
					ImGui::Separator();
				}
			}
			else if (isRetrival) {
				ImGui::Text("请点击加入模型特征库库");
			}
		}
		else {
			ImGui::Text("请打开文件");
		}
		ImGui::End();


        //Rendering       
        ImGuiIO& io = ImGui::GetIO();
        io.DisplaySize = ImVec2(WinWidth, WinHeight);
        ImGui::Render();
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        if (io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable)
        {
            GLFWwindow* backup_current_context = glfwGetCurrentContext();
            ImGui::UpdatePlatformWindows();
            ImGui::RenderPlatformWindowsDefault();
            glfwMakeContextCurrent(backup_current_context);
        }

        //3.一帧结束
        glfwPollEvents();
        glfwSwapBuffers(window);

        if(toTakePictures) { //一帧结束后对该帧截图
            if (pictureIndex < VIEWCOUNT * 2) {
                TakingPicture(display.GetTexID(), App.GetCADName(), App.GetPictureExportPath(isMBDView));
            }
            else {
                //TakingPicture(App.GetCADName(), App.GetModelPictureExportPath());
            }
            pictureIndex++;
        }
    }

    //销毁
	Py_Finalize;

	if (swStateMap[MyApp::SWState::Connected] == MyApp::MyState::Succeed) {
		CoUninitialize();
	}

    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();

    glfwDestroyWindow(window);
    glfwTerminate();

    return 0;
}
