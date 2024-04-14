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

#include <stack> //栈

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
unsigned int WinWidth = 600;
unsigned int WinHeight = 600;
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

bool TakingPicture(std::string fileName, std::string filePath) { //截屏并保存
	unsigned char* picture = new unsigned char[WinWidth * WinHeight * 3];
	glReadPixels(0, 0, WinWidth, WinHeight, GL_BGR, GL_UNSIGNED_BYTE, picture);

    std::string name = filePath + fileName + "_" + std::to_string((int)viewDirction) + "_" + std::to_string((int)viewType) + "_" + std::to_string((int)cullMode) + ".bmp";
	FILE* pFile = fopen(name.c_str(), "wb");
	if (pFile) {
		BITMAPFILEHEADER bfh;
		memset(&bfh, 0, sizeof(BITMAPFILEHEADER));
		bfh.bfType = 0x4D42;
		bfh.bfSize = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER) + WinWidth * WinHeight * 3;
		bfh.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
		fwrite(&bfh, sizeof(BITMAPFILEHEADER), 1, pFile);
		BITMAPINFOHEADER bih;
		memset(&bih, 0, sizeof(BITMAPINFOHEADER));
		bih.biWidth = WinWidth;
		bih.biHeight = WinHeight;
		bih.biBitCount = 24;
		bih.biSize = sizeof(BITMAPINFOHEADER);
		fwrite(&bih, sizeof(BITMAPINFOHEADER), 1, pFile);
		fwrite(picture, 1, WinWidth * WinHeight * 3, pFile);
		fclose(pFile);

	}
    else {
        return false;
    }
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
		if (Cross(stack.top(), plist[i]) < 0.000001 && Cross(stack.top(), plist[i]) > -0.000001) {//点在线上
			stack.push(plist[i]);
		}
		else if (Cross(stack.top(), plist[i]) < 0)//在栈顶点与原点连线的右边
		{
			stack.pop();
			stack.push(plist[i]);
		}
		else {
			glm::vec2 p1 = stack.top();
			stack.pop();
			glm::vec2 p2 = stack.top();
			if (getangle(plist[i], p1, p2) <= 0) {//负角且是钝角，保留
				stack.push(p1);
				stack.push(plist[i]);
			}
			else {//正角，舍去
				while (getangle(plist[i], p1, p2) > 0)
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
		std::string filePath = App.GetExportPath();
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

// Main code
//int main(int, char**)
int WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
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
    GLFWwindow* window = glfwCreateWindow(WinWidth, WinHeight, "Display", nullptr, nullptr);
    if (window == nullptr) {
        glfwTerminate();
        return 1;
    }       
    glfwMakeContextCurrent(window);
    glfwSwapInterval(0); //1=开启垂直同步

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
            std::string name = App.GetNextToOpenFileName();
            if (name != "") {
				//1.打开文件
				App.StartOpenFile(name);
				//2.读取属性
				App.StartReadProperty();
				//3.加载质量
				App.StartReadMassProperty();
				//4.读取MBD特征及其标注
				App.StartReadMBD();
                faceMap = App.GetFaceMap();
				//5.加载模型
				App.StartLoadModel();
                LoadModel(modelMap, instanceMap);
				//6.准许拍照
				toTakePictures = true;
                pictureIndex = 0;
				lastFileFinished = false;
                //7.保存略缩图
                CString modelPicturePath;
				std::string modelPicturePathStr = App.GetModelPictureExportPath() + App.GetCADName() + "_.bmp";
                modelPicturePath = CA2T(modelPicturePathStr.c_str());
                App.SaveBitmapToFile(App.GetThumbnailEx(), modelPicturePath);
            }
            else {
                App.StopAutomatization();//如果文件读取完毕就停止自动化
            }
            
        }

		//设定拍照模式
		if (toTakePictures) {
			if (pictureIndex < VIEWCOUNT + 1) {
				viewDirction = (ViewDirection)(picturesType[pictureIndex][0]);
				viewType = (ViewType)(picturesType[pictureIndex][1]);
				cullMode = (CullMode)(picturesType[pictureIndex][2]);
			}
			else {
				toTakePictures = false;
				lastFileFinished = true;//18张截图拍完后说明要换下一CAD文件
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
		glEnable(GL_DEPTH_TEST);
		renderer.ClearColor(1.0f, 1.0f, 1.0f, 1.0f);
		renderer.ClearDepth();
		renderer.CullFace((int)cullMode);

		shader.Bind();
		if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed) {
			for (auto model : modelMap) {
                ViewType tempViewType = App.ShouldShowMBD() ? viewType : ViewType::Diffuse;
                glm::vec3 MBDColor = GetRGB(faceMap[model.first], tempViewType);
                shader.SetUniform3f("MBDColor", MBDColor.x, MBDColor.y, MBDColor.z);
                shader.SetUniform1i("viewType", (int)tempViewType);
				model.second.DrawInstanced(shader, 1);
			}
		}
		shader.Unbind();

		glDisable(GL_CULL_FACE);
		convexHullShader.Bind();
		if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed) {
			for (auto model : convexHullModelList) {
				model.DrawInstanced(convexHullShader, 1);
			}
		}
		convexHullShader.Unbind();
		

        //2.渲染ImGui界面
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        //MyApp		
		App.ShowMyApp();
        
        ImGui::Begin("Debug");
        //获取OpenGL错误信息	
		ImGui::Text(("OpenGL: " + std::to_string(GLCheckError())).c_str());
        //截图
        ImGui::Checkbox("旋转?", &toRotate);
        if (ImGui::Button("保存视图") ) {
            TakingPicture(App.GetCADName(), App.GetExportPath());
        }
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
        ImGui::RadioButton("基准_粗糙度_粗糙度值", (int*)&viewType, (int)ViewType::IsDatum_IsSFSymbol_AccuracySize);
        ImGui::RadioButton("形位公差_公差值_实体状态", (int*)&viewType, (int)ViewType::IsGeoTolerance_AccuracySize_hasMCM);
        ImGui::RadioButton("尺寸公差_尺寸值_公差值", (int*)&viewType, (int)ViewType::IsDimTolerance_DimSize_AccuracySize);
		ImGui::RadioButton("漫反射", (int*)&viewType, (int)ViewType::Diffuse);
        ImGui::Separator();
		//剔除模式选择
		ImGui::RadioButton("剔除反面", (int*)&cullMode, (int)CullMode::CullBack);
		ImGui::SameLine();
		ImGui::RadioButton("剔除正面", (int*)&cullMode, (int)CullMode::CullFront);
        ImGui::Separator();
        //耗时显示
        ImGui::Text("MBD读取总耗时=%f", (float)App.allTime);
        ImGui::Text("特征读取耗时(包含标注、面耗时)=%f", (float)App.feTime);
        ImGui::Text("标注读取耗时=%f", (float)App.aTime);
        ImGui::Text("面读取循环耗时=%f", (float)App.fTime);
        ImGui::Text("表面粗糙度读取耗时=%f", (float)App.swaTime);
        ImGui::Text("非MBD面读取耗时=%f", (float)App.bTime);
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
            if (pictureIndex < VIEWCOUNT) {
                TakingPicture(App.GetCADName(), App.GetPictureExportPath());
            }
            else {
                //TakingPicture(App.GetCADName(), App.GetModelPictureExportPath());
            }
            pictureIndex++;
        }
    }

    //销毁
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();

    glfwDestroyWindow(window);
    glfwTerminate();

    return 0;
}
