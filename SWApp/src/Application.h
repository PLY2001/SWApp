#pragma once
#include <unordered_map>
#include <map>
//#include <string>
//#include <atlstr.h>
//#include <memory>
//#include <mutex>
#include <regex>//正则表达式
#include "glm/glm.hpp"
#include "glm/gtc/matrix_transform.hpp"
#include "glm/gtc/type_ptr.hpp"

//SolidWorks
#include <atlbase.h> //com
#import "sldworks.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  // SOLIDWORKS type library
#import "swconst.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids   // SOLIDWORKS constants type library
#import "swdimxpert.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  //SOLIDWORKS dimxpert library

namespace MyApp {

	struct MyAnnotation { //若有俩面之间的尺寸公差标注，那么这俩面都具有一样的MyAnnotation，但是定义在不同的MyFaceFeature中
		std::string Name;//标注名称
		swDimXpertAnnotationType_e Type = swDimXpertAnnotationType_unknown;//标注类型
		double AccuracySize = 0;//公差或粗糙度精度(毫米)
		int AccuracyLevel = 0;//公差或粗糙度等级
		
		//标注基准
		int IsDatum = 0;//是否是标注基准
		std::string DatumName;//基准名称

		//表面粗糙度
		int IsSFSymbol = 0;//是否是表面粗糙度
		swSFSymType_e SFSType = swSFBasic;//表面粗糙度类型

		//公差
		int IsTolerance = 0;//是否是尺寸/形位公差
		std::vector<std::string> ToleranceDatumNames;//公差基准
		int hasMCM = 0;//形位公差是否有实体状态
		swDimXpertMaterialConditionModifier_e MCMType = swDimXpertMaterialConditionModifier_unknown;//实体状态类型，即形位公差标注中的M和L

	};//标注 

	struct MyFaceFeature {
		std::string Name;//特征名称
		//CComBSTR AppliedFaceNameBSTR;//所属面名称
		int AnnotationCount = 0;//标注数量
		std::vector<MyAnnotation> AnnotationArray;//标注数组
	};//特征面

	enum class MyState {
		Nothing, Succeed, Failed
	};//程序当前操作状态
	enum class SWState {
		Connected, FileOpen, PropertyGot, MBDGot, ModelLoaded, MassPropertyGot
	};//SW交互状态

	class MyApplication {
	private:
		std::map<std::string, std::string> property;//记录自定义属性
		std::map<std::string, std::string> summary;//记录摘要

		std::string MyStateMessage[3] = { "Unfinished","Succeed!","Failed!" };//提示文本		
		std::map<SWState, MyState> SWStateMap = {
			 {SWState::Connected,   MyState::Nothing}
			,{SWState::FileOpen,    MyState::Nothing}
			,{SWState::PropertyGot, MyState::Nothing}
			,{SWState::MBDGot,      MyState::Nothing}
			,{SWState::ModelLoaded, MyState::Nothing}
			,{SWState::MassPropertyGot, MyState::Nothing}
		};//记录SW交互状态
		MyState myState = MyState::Nothing;//记录程序当前操作状态

		bool toLoad = false;//是否弹出项目地址窗口
		
		long DimXpertAnnotationCount = 0;//MBD标注数
		long DimXpertFeatureCount = 0;//MBD特征数

		std::unordered_map<std::string, MyFaceFeature> FaceMap;//记录MBD信息[面 : 特征(标注1，标注2...)]
		
		std::unordered_map<swDimXpertAnnotationType_e, int> GeoTolMap = {
			 {swDimXpertGeoTol_Angularity              ,2}//倾斜度M
			,{swDimXpertGeoTol_Circularity			   ,1}//圆度
			,{swDimXpertGeoTol_CircularRunout		   ,1}//圆跳动度
			,{swDimXpertGeoTol_CompositeLineProfile	   ,1}//复合 线轮廓度？
			,{swDimXpertGeoTol_CompositePosition	   ,2}//复合 位置度M？
			,{swDimXpertGeoTol_CompositeSurfaceProfile ,1}//复合 面轮廓度？
			,{swDimXpertGeoTol_Concentricity		   ,2}//同心度、同轴度M
			,{swDimXpertGeoTol_Cylindricity			   ,1}//圆柱度
			,{swDimXpertGeoTol_Flatness				   ,1}//平面度
			,{swDimXpertGeoTol_LineProfile			   ,1}//线轮廓度
			,{swDimXpertGeoTol_Parallelism			   ,2}//平行度M
			,{swDimXpertGeoTol_Perpendicularity		   ,2}//垂直度M
			,{swDimXpertGeoTol_Position				   ,2}//位置度M
			,{swDimXpertGeoTol_Straightness			   ,2}//直线度M
			,{swDimXpertGeoTol_SurfaceProfile		   ,1}//面轮廓度
			,{swDimXpertGeoTol_Symmetry				   ,2}//对称度M
			,{swDimXpertGeoTol_Tangency				   ,1}//切线度？
			,{swDimXpertGeoTol_TotalRunout			   ,1}//全跳动
		};//MBD标注类型集合：形位公差
		std::unordered_map<swDimXpertAnnotationType_e, int> DimTolMap = {
			 {swDimXpertDimTol_AngleBetween            ,1}//面间夹角公差
			,{swDimXpertDimTol_ChamferDimension		   ,1}//倒角公差
			,{swDimXpertDimTol_CompositeDistanceBetween,1}//面间混合距离公差？
			,{swDimXpertDimTol_ConeAngle			   ,1}//圆锥角公差
			,{swDimXpertDimTol_CounterBore			   ,1}//反向钻孔公差
			,{swDimXpertDimTol_CounterSinkAngle		   ,1}//反向沉头角度公差
			,{swDimXpertDimTol_CounterSinkDiameter	   ,1}//反向沉头直径公差
			,{swDimXpertDimTol_Depth				   ,1}//深度公差
			,{swDimXpertDimTol_Diameter				   ,1}//直径公差
			,{swDimXpertDimTol_DistanceBetween		   ,1}//面间距离公差
			,{swDimXpertDimTol_Length				   ,1}//长度公差
			,{swDimXpertDimTol_PatternAngleBetween	   ,1}//图案间角度公差
			,{swDimXpertDimTol_Radius				   ,1}//半径公差
			,{swDimXpertDimTol_Width				   ,1}//宽度公差
		};//MBD标注类型集合：尺寸公差

		bool toSave = true;//读取MBD时是否要保存模型

		char InputName[64] = "pipe";//用户输入名
		std::string CADName = InputName;//默认CAD文件名
		std::string CADType = ".SLDPRT";//默认CAD文件类型
		std::string CADPath = "D:\\Projects\\SWApp\\SolidWorks Part\\";//默认CAD文件路径

		glm::vec3 MassCenter = glm::vec3(0);
			
		void EnableDocking();//开启Docking特性
		void ShowMenuBar();//显示菜单栏
		void ShowImguiExample();//显示Imgui示例
		bool ShowMessage(const char* message);//显示ImGui弹窗，而ImGui::OpenPopup("提示")用于弹出弹窗
		bool ConnectSW();//连接SW
		bool OpenFile();//打开文件
		bool ReadProperty();//读取文件属性
		bool ReadMBD();//读取MBD特征及其标注
		bool LoadModel();//加载模型
		bool ReadMassProperty();//获取质量属性

		std::string GbkToUtf8(const char* src_str);//将SW默认文本的GBK编码转为ImGui显示文本用的Utf8编码
		bool ReadSafeArray(VARIANT* vt, VARENUM vtType, int dimensional, LPVOID* pData, LONG* itemCount);//读取SAFEARRAY数组(输入VARIANT变量，数组元素类型，数组维度，输出数组，输出数组大小)
		template<typename T>
		bool CreatVARIANTArray(int size, VARENUM type, T* buffer, VARIANT* array);//创建含SAFEARRAY的VARIANT变量(数组大小，数组元素类型，输入数组，输出VARIANT变量)
		double ReadDoubleFromString(std::string textstr);//读取字符串中的小数，如6.3
		
		void ReadAnnotationData(swDimXpertAnnotationType_e annoType,double* toleranceSize, int* toleranceLevel,std::string* myDatumName, std::vector<std::string>& datumNames,swDimXpertMaterialConditionModifier_e* MCMType);//读取标注数据
		void DatumData(std::string* myDatumName);//读取基准信息
		void GeoTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel, std::vector<std::string>& datumNames, swDimXpertMaterialConditionModifier_e* MCMType);//读取形位公差数据
		void DimTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel);//读取尺寸公差数据
	
	public:
		void ShowMyApp();
		inline std::unordered_map<std::string, MyFaceFeature>& GetFaceMap() { return FaceMap; };//获取面哈希表的引用
		inline std::map<SWState, MyState>& GetSWStateMap() { return SWStateMap; };//获取SW交互状态的引用
		inline std::string GetExportPath() { return CADPath + CADName + "\\"; };//获取保存模型时的路径
		inline glm::vec3 GetMassCenter() { return MassCenter; };//获取质心(毫米)

	//极致简洁的单例模式，运用了static的性质
	private:
		static std::shared_ptr<MyApplication> instance;
		
		MyApplication() {};
		~MyApplication() {};
	public:
		static MyApplication& GetInstance() {
			static MyApplication instance;
			return instance;
		}
		

	};

	


    
}
